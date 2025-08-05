import streamlit as st
import pandas as pd
import os
import datetime
import altair as alt
import requests
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh

# Carga variables de entorno
load_dotenv()
ONESIGNAL_APP_ID = os.getenv("ONESIGNAL_APP_ID")
ONESIGNAL_API_KEY = os.getenv("ONESIGNAL_REST_API_KEY")
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")

st.set_page_config(page_title="Seguimiento de Pedidos", layout="wide", initial_sidebar_state="collapsed")

# Estilos
st.markdown("""
    <style>
    body, .stApp {
        background-color: #0e1117;
        color: #ffffff;
    }
    .card {
        background-color: #1f2630;
        padding: 1rem;
        border-radius: 12px;
        box-shadow: 0px 0px 10px #222;
        margin-bottom: 1rem;
    }
    .card h4 {
        margin-top: 0;
    }
    </style>
""", unsafe_allow_html=True)

# Función para enviar notificación push
def send_push_notification(destino):
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Basic {ONESIGNAL_API_KEY}"
    }
    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "included_segments": ["All"],
        "filters": [{"field": "tag", "key": "destino", "relation": "=", "value": destino}],
        "contents": {"en": f"📦 El estatus del pedido con destino {destino} ha cambiado."},
        "headings": {"en": "Nuevo cambio de estatus"},
    }
    requests.post("https://onesignal.com/api/v1/notifications", json=payload, headers=headers)

# Función para suscribirse al destino actual
def subscribe_to_destino(destino):
    st.markdown(f"""
        <script>
            if (window.OneSignal) {{
                OneSignal.push(function() {{
                    OneSignal.sendTag("destino", "{destino}").then(function(tags) {{
                        console.log("Destino suscrito:", tags);
                        alert("✅ Suscrito correctamente al destino {destino}. Recibirás notificaciones de cambios.");
                    }});
                }});
            }}
        </script>
    """, unsafe_allow_html=True)

# Función para mostrar tarjetas de datos
def mostrar_tarjetas(df_filtrado):
    for _, row in df_filtrado.iterrows():
        with st.container():
            st.markdown(f"""
                <div class="card">
                    <h4>🛒 {row['Producto']}</h4>
                    <p><strong>Turno:</strong> {row['Turno']}</p>
                    <p><strong>Tonel:</strong> {row['Tonel']}</p>
                    <p><strong>Capacidad:</strong> {row['Capacidad programada (Litros)']} L</p>
                    <p><strong>Fecha estimada:</strong> {row['Fecha y hora estimada']}</p>
                    <p><strong>Fecha facturación:</strong> {row['Fecha y hora de facturación']}</p>
                    <p><strong>Estatus:</strong> {row['Estado de atención']}</p>
                </div>
            """, unsafe_allow_html=True)

# Función para login de administrador
def login_panel():
    with st.sidebar:
        st.markdown("## 🔐 Acceso administrador")
        user = st.text_input("Usuario")
        pwd = st.text_input("Contraseña", type="password")
        if st.button("Iniciar sesión"):
            if user == ADMIN_USER and pwd == ADMIN_PASS:
                st.session_state["admin_logged"] = True
                st.experimental_rerun()
            else:
                st.error("Credenciales incorrectas")

# Función sección admin
def admin_panel():
    st.title("Panel de Administración")
    archivo = st.file_uploader("📤 Cargar archivo de pedidos (Excel)", type=["xlsx"])
    if archivo:
        nuevo_df = pd.read_excel(archivo)
        try:
            historico = pd.read_excel("historico_estatus.xlsx")
        except FileNotFoundError:
            historico = pd.DataFrame()

        nuevo_df["ID"] = nuevo_df["Destino"].astype(str) + " | " + pd.to_datetime(nuevo_df["Fecha"]).dt.strftime("%Y-%m-%d")

        if not historico.empty:
            historico["ID"] = historico["Destino"].astype(str) + " | " + pd.to_datetime(historico["Fecha"]).dt.strftime("%Y-%m-%d")
            df_comb = pd.merge(nuevo_df, historico, on="ID", how="left", suffixes=('', '_old'))
            df_novedades = df_comb[df_comb["Estado de atención"] != df_comb["Estado de atención_old"]]
        else:
            df_novedades = nuevo_df.copy()

        if not df_novedades.empty:
            for destino in df_novedades["Destino"].unique():
                send_push_notification(destino)

        df_final = pd.concat([historico, nuevo_df], ignore_index=True).drop_duplicates(subset=["ID"], keep="last")
        df_final.to_excel("historico_estatus.xlsx", index=False)
        st.success("✅ Archivo procesado y actualizado.")
    else:
        st.warning("Por favor, carga un archivo Excel.")

# Función sección usuarios
def usuario_panel():
    st.title("🔍 Consulta tu pedido por destino")

    try:
        historico = pd.read_excel("historico_estatus.xlsx")
    except FileNotFoundError:
        st.error("No hay datos disponibles aún.")
        return

    historico["Destino_str"] = historico["Destino"].astype(str)

    query = st.text_input("🔎 Escribe tu número de destino:")
    if query:
        df_filtrado = historico[historico["Destino_str"].str.contains(query)]
        if not df_filtrado.empty:
            destino_actual = df_filtrado["Destino"].iloc[0]
            if st.button("🔔 Suscribirme a notificaciones de este destino"):
                subscribe_to_destino(destino_actual)
            mostrar_tarjetas(df_filtrado[[
                "Producto", "Turno", "Tonel", "Capacidad programada (Litros)",
                "Fecha y hora estimada", "Fecha y hora de facturación", "Estado de atención"
            ]])
        else:
            st.info("No se encontraron pedidos para ese destino.")

# Función principal
def main():
    if "admin_logged" not in st.session_state:
        st.session_state["admin_logged"] = False

    modo = st.sidebar.radio("Selecciona el modo:", ["Consulta Usuario", "Administrador"])
    if modo == "Administrador":
        if not st.session_state["admin_logged"]:
            login_panel()
        else:
            admin_panel()
    else:
        usuario_panel()

# Ejecutar app
if __name__ == "__main__":
    main()
