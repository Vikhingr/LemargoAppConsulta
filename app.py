import streamlit as st
import pandas as pd
import os
import requests
from dotenv import load_dotenv

# Carga variables de entorno
load_dotenv()
ONESIGNAL_APP_ID = os.getenv("ONESIGNAL_APP_ID")
ONESIGNAL_API_KEY = os.getenv("ONESIGNAL_REST_API_KEY")
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")

st.set_page_config(page_title="Seguimiento de Pedidos", layout="wide", initial_sidebar_state="collapsed")

# Estilos globales
st.markdown("""
    <style>
    body, .stApp {
        background-color: #0e1117;
        color: #ffffff;
    }
    .card {
        padding: 0.75rem 1rem;
        border-radius: 12px;
        box-shadow: 0px 0px 10px #0003;
        margin-bottom: 1rem;
        font-size: 0.9rem;
    }
    .card h4 {
        margin-top: 0;
        margin-bottom: 0.5rem;
    }
    .blue { background-color: #1f3b70; }
    .yellow { background-color: #665c00; }
    .green { background-color: #1f703b; }
    .red { background-color: #701f1f; }
    </style>
""", unsafe_allow_html=True)

# Enviar notificación
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

# Suscripción a notificación
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

# Color según estado
def get_card_class(estado):
    estado = str(estado).lower()
    if "cancel" in estado:
        return "red"
    elif "factur" in estado:
        return "green"
    elif "program" in estado:
        return "blue"
    elif "carg" in estado:
        return "yellow"
    return "blue"

# Mostrar tarjetas compactas
def mostrar_tarjetas(df_filtrado):
    for _, row in df_filtrado.iterrows():
        estado_class = get_card_class(row['Estado de atención'])
        st.markdown(f"""
            <div class="card {estado_class}">
                <h4>🛒 {row['Producto']}</h4>
                <p>👷 <strong>Turno:</strong> {row['Turno']}</p>
                <p>🛢️ <strong>Tonel:</strong> {row['Tonel']}</p>
                <p>📏 <strong>Capacidad:</strong> {row['Capacidad programada (Litros)']} L</p>
                <p>📅 <strong>Fecha estimada:</strong> {row['Fecha y hora estimada']}</p>
                <p>🧾 <strong>Fecha facturación:</strong> {row['Fecha y hora de facturación']}</p>
                <p>🚦 <strong>Estado:</strong> {row['Estado de atención']}</p>
            </div>
        """, unsafe_allow_html=True)

# Login admin
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

# Panel admin
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

# Panel usuario
def usuario_panel():
    st.title("🔍 Consulta tu pedido por número de destino")

    try:
        historico = pd.read_excel("historico_estatus.xlsx")
    except FileNotFoundError:
        st.error("No hay datos disponibles aún.")
        return

    historico["Destino_str"] = historico["Destino"].astype(str)

    query = st.text_input("🔎 Escribe solo el número de tu destino (ej. 58):")
    if query:
        numero = query.strip()
        df_filtrado = historico[historico["Destino_str"].str.fullmatch(numero)]

        if not df_filtrado.empty:
            destino_actual = numero

            if st.button("🔔 Suscribirme a notificaciones de este destino"):
                subscribe_to_destino(destino_actual)

            mostrar_tarjetas(df_filtrado[[
                "Producto", "Turno", "Tonel", "Capacidad programada (Litros)",
                "Fecha y hora estimada", "Fecha y hora de facturación", "Estado de atención"
            ]])
        else:
            st.info("⚠️ No se encontraron pedidos exactos para ese número de destino.")

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

if __name__ == "__main__":
    main()
