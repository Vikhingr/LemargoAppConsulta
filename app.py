import streamlit as st
import pandas as pd
import os
import requests
from datetime import datetime

# ================== CONFIGURACIÓN ==================
st.set_page_config(page_title="Seguimiento de Pedidos", layout="wide")

# ================== ESTILOS ==================
st.markdown("""
    <style>
    .card {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        font-family: Arial, sans-serif;
    }
    .cancelado { background-color: #ff4b4b; color: white; }
    .entregado { background-color: #4CAF50; color: white; }
    .pendiente { background-color: #FFD700; color: black; }
    .en_transito { background-color: #1E90FF; color: white; }
    </style>
""", unsafe_allow_html=True)

# ================== SECRETS ==================
ONESIGNAL_APP_ID = st.secrets["ONESIGNAL_APP_ID"]
ONESIGNAL_API_KEY = st.secrets["ONESIGNAL_REST_API_KEY"]
ADMIN_USER = st.secrets["ADMIN_USER"]
ADMIN_PASS = st.secrets["ADMIN_PASS"]

# ================== NOTIFICACIÓN ==================
def send_push_notification(destino):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {ONESIGNAL_API_KEY}"
    }
    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "filters": [{"field": "tag", "key": "destino", "relation": "=", "value": destino}],
        "headings": {"en": "Actualización de Pedido"},
        "contents": {"en": f"Hay un cambio en el estado de pedidos para {destino}."}
    }
    requests.post("https://onesignal.com/api/v1/notifications", headers=headers, json=payload)

# ================== LOGIN ==================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

with st.sidebar:
    st.title("Administrador")
    if not st.session_state.logged_in:
        user = st.text_input("Usuario")
        pwd = st.text_input("Contraseña", type="password")
        if st.button("Ingresar"):
            if user == ADMIN_USER and pwd == ADMIN_PASS:
                st.session_state.logged_in = True
                st.success("Acceso concedido")
            else:
                st.error("Credenciales inválidas")
    else:
        st.success("Sesión iniciada")

# ================== CARGA Y COMPARACIÓN ==================
if st.session_state.logged_in:
    st.subheader("📤 Cargar nuevo archivo de pedidos")
    file = st.file_uploader("Selecciona el archivo Excel", type=["xlsx"])
    if file:
        nuevo_df = pd.read_excel(file)
        nuevo_df["Fecha Consulta"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        nuevo_df["Fuente"] = "nuevo_datos.xlsx"
        nuevo_df["ID"] = nuevo_df["Destino"].astype(str) + "_" + nuevo_df["Fecha"].astype(str)

        # Cargar histórico si existe
        if os.path.exists("historico_estatus.xlsx"):
            historico_df = pd.read_excel("historico_estatus.xlsx")
        else:
            historico_df = pd.DataFrame(columns=nuevo_df.columns)

        # Combinar sin duplicados
        combinados = pd.concat([historico_df, nuevo_df], ignore_index=True)
        combinados = combinados.drop_duplicates(subset=["ID", "Estado de atención"], keep="last")

        # Detectar cambios de estatus
        cambios = []
        for idx, row in nuevo_df.iterrows():
            filtro = (historico_df["ID"] == row["ID"]) & (historico_df["Estado de atención"] != row["Estado de atención"])
            if historico_df[filtro].shape[0] > 0:
                cambios.append(row["Destino"])

        if cambios:
            destinos_afectados = list(set(cambios))
            for destino in destinos_afectados:
                send_push_notification(destino)

        # Guardar histórico actualizado
        combinados.to_excel("historico_estatus.xlsx", index=False)
        st.success("✅ Archivo procesado y guardado en el histórico.")

# ================== CONSULTA USUARIO ==================
st.header("🔍 Consultar pedidos por destino")
destino_input = st.text_input("Escribe el número exacto del destino").strip()

if destino_input:
    if not os.path.exists("historico_estatus.xlsx"):
        st.warning("No hay datos disponibles todavía.")
    else:
        historico = pd.read_excel("historico_estatus.xlsx")
        resultados = historico[historico["Destino"].astype(str) == destino_input]

        if resultados.empty:
            st.info("No se encontraron pedidos para ese destino.")
        else:
            resultados = resultados.sort_values(by="Fecha Consulta", ascending=False)
            columnas_mostrar = [
                "Producto", "Turno", "Tonel",
                "Capacidad programada (Litros)",
                "Fecha y hora estimada", "Fecha y hora de facturación",
                "Estado de atención"
            ]
            for _, row in resultados.iterrows():
                estado = str(row["Estado de atención"]).lower()
                clase = "card"
                if "cancelado" in estado:
                    clase += " cancelado"
                elif "entregado" in estado:
                    clase += " entregado"
                elif "pendiente" in estado:
                    clase += " pendiente"
                else:
                    clase += " en_transito"

                contenido = ""
                for col in columnas_mostrar:
                    if col in row:
                        contenido += f"<b>{col}:</b> {row[col]}<br>"

                st.markdown(f'<div class="{clase}">{contenido}</div>', unsafe_allow_html=True)

            # Botón de suscripción personalizado
            st.markdown(f"""
                <script src="https://cdn.onesignal.com/sdks/OneSignalSDK.js" async=""></script>
                <script>
                  window.OneSignal = window.OneSignal || [];
                  OneSignal.push(function() {{
                    OneSignal.init({{
                      appId: "{ONESIGNAL_APP_ID}",
                    }});
                    OneSignal.showSlidedownPrompt();
                    OneSignal.sendTag("destino", "{destino_input}");
                  }});
                </script>
            """, unsafe_allow_html=True)
