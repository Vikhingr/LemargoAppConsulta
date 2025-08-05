import streamlit as st
import pandas as pd
import os
import requests
from datetime import datetime

# ======================= CONFIGURACIÓN =======================
st.set_page_config(page_title="Seguimiento de Pedidos", layout="wide")

# ======================= ESTILOS =======================
st.markdown("""
    <style>
    body {
        background-color: #0e1117;
        color: #ffffff;
    }
    .css-1d391kg {padding-top: 1rem;}
    .card {
        background-color: #262730;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    .cancelado { background-color: #ff4b4b; color: white; }
    .entregado { background-color: #4CAF50; color: white; }
    .pendiente { background-color: #FFA500; color: black; }
    .en_transito { background-color: #1E90FF; color: white; }
    </style>
""", unsafe_allow_html=True)

# ======================= SECRETS =======================
ONESIGNAL_APP_ID = st.secrets["ONESIGNAL_APP_ID"]
ONESIGNAL_API_KEY = st.secrets["ONESIGNAL_REST_API_KEY"]
ADMIN_USER = st.secrets["ADMIN_USER"]
ADMIN_PASS = st.secrets["ADMIN_PASS"]

# ======================= FUNCIÓN ONESIGNAL =======================
def send_push_notification(destino):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {ONESIGNAL_API_KEY}"
    }
    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "included_segments": ["All"],
        "filters": [
            {"field": "tag", "key": "destino", "relation": "=", "value": destino}
        ],
        "headings": {"en": "Actualización de Pedido"},
        "contents": {"en": f"Hay un cambio en el estado de pedidos para {destino}."}
    }
    response = requests.post("https://onesignal.com/api/v1/notifications", headers=headers, json=payload)
    return response.status_code

# ======================= LOGIN =======================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

with st.sidebar:
    st.title("Administrador")
    if not st.session_state.logged_in:
        user = st.text_input("Usuario")
        pwd = st.text_input("Contraseña", type="password")
        if st.button("Ingresar"):
            if user == ADMIN_USER and pwd == ADMIN_PASS:
                st.success("Acceso concedido")
                st.session_state.logged_in = True
            else:
                st.error("Credenciales inválidas")
    else:
        st.success("Sesión iniciada")

# ======================= CARGA DE ARCHIVO =======================
if st.session_state.logged_in:
    st.subheader("📤 Cargar archivo de pedidos")
    file = st.file_uploader("Selecciona el archivo Excel", type=["xlsx"])
    if file:
        df = pd.read_excel(file)
        st.write("Vista previa de los datos:")
        st.dataframe(df.head())

        # Validar columnas necesarias
        columnas_requeridas = ['Destino', 'Fecha', 'Estado de atención', 'Folio Pedido']
        if not all(col in df.columns for col in columnas_requeridas):
            st.error("❌ El archivo no contiene las columnas necesarias.")
        else:
            # Métricas
            st.subheader("📊 Métricas")
            total = len(df)
            entregados = len(df[df['Estado de atención'].str.contains("entregado", case=False, na=False)])
            cancelados = len(df[df['Estado de atención'].str.contains("cancelado", case=False, na=False)])
            pendientes = total - entregados - cancelados

            col1, col2, col3 = st.columns(3)
            col1.metric("Total pedidos", total)
            col2.metric("Entregados", entregados)
            col3.metric("Cancelados", cancelados)

            # Gráfica
            st.bar_chart(df['Estado de atención'].value_counts())

# ======================= CONSULTA PÚBLICA =======================
st.header("🔍 Consultar pedidos por destino")

destino_input = st.text_input("Escribe el destino (no es necesario escribirlo completo)").strip()

if destino_input:
    if 'df' not in locals():
        st.warning("⚠️ No hay datos cargados todavía.")
    else:
        resultados = df[df['Destino'].str.contains(destino_input, case=False, na=False)]
        if resultados.empty:
            st.warning("No se encontraron pedidos para ese destino.")
        else:
            for _, row in resultados.iterrows():
                estado = row['Estado de atención'].lower()
                clase = "card"
                if "cancelado" in estado:
                    clase += " cancelado"
                elif "entregado" in estado:
                    clase += " entregado"
                elif "pendiente" in estado:
                    clase += " pendiente"
                else:
                    clase += " en_transito"
                st.markdown(f"""
                    <div class="{clase}">
                        <strong>Destino:</strong> {row['Destino']}<br>
                        <strong>Folio:</strong> {row['Folio Pedido']}<br>
                        <strong>Estado:</strong> {row['Estado de atención']}<br>
                        <strong>Fecha:</strong> {row['Fecha']}<br>
                    </div>
                """, unsafe_allow_html=True)

            # ======== BOTÓN DE SUSCRIPCIÓN ONESIGNAL =========
            st.markdown("""
                <script src="https://cdn.onesignal.com/sdks/OneSignalSDK.js" async=""></script>
                <script>
                  window.OneSignal = window.OneSignal || [];
                  OneSignal.push(function() {
                    OneSignal.init({
                      appId: "%s",
                    });
                    OneSignal.showSlidedownPrompt();
                    OneSignal.sendTag("destino", "%s");
                  });
                </script>
            """ % (ONESIGNAL_APP_ID, destino_input), unsafe_allow_html=True)
