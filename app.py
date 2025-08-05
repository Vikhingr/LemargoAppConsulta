import streamlit as st
import pandas as pd
import numpy as np
import os
import datetime
import altair as alt
import requests
from streamlit_autorefresh import st_autorefresh
from dotenv import load_dotenv

# Cargar variables del archivo .env o secrets.toml
load_dotenv()
ONESIGNAL_APP_ID = os.getenv("ONESIGNAL_APP_ID", st.secrets.get("ONESIGNAL_APP_ID"))
ONESIGNAL_REST_API_KEY = os.getenv("ONESIGNAL_REST_API_KEY", st.secrets.get("ONESIGNAL_REST_API_KEY"))
ADMIN_USER = os.getenv("ADMIN_USER", st.secrets.get("ADMIN_USER"))
ADMIN_PASS = os.getenv("ADMIN_PASS", st.secrets.get("ADMIN_PASS"))

# Configuración inicial
st.set_page_config(page_title="Seguimiento de Pedidos", layout="wide", initial_sidebar_state="auto")

# Estilos generales
st.markdown("""
    <style>
        body {
            background-color: #0E1117;
            color: white;
        }
        .block-container {
            padding-top: 2rem;
        }
        .stButton>button {
            background-color: #444 !important;
            color: white !important;
        }
        .stTextInput>div>input {
            color: white !important;
        }
    </style>
""", unsafe_allow_html=True)

# Archivos clave
HISTORICO_PATH = "historico_estatus.xlsx"
NUEVO_DATOS_PATH = "nuevo_datos.xlsx"

# Función para cargar histórico
def cargar_historico():
    if os.path.exists(HISTORICO_PATH):
        return pd.read_excel(HISTORICO_PATH)
    else:
        return pd.DataFrame()

# Función para detectar cambios
def detectar_cambios(df_nuevo, df_hist):
    df_nuevo["ID"] = df_nuevo["Destino"].astype(str) + df_nuevo["Fecha"].astype(str)
    df_hist["ID"] = df_hist["Destino"].astype(str) + df_hist["Fecha"].astype(str)

    cambios = df_nuevo[~df_nuevo["ID"].isin(df_hist["ID"])]
    return cambios

# Función para guardar histórico
def guardar_historico(df):
    df.to_excel(HISTORICO_PATH, index=False)

# Función para enviar notificación
def enviar_notificacion(destino, mensaje):
    url = "https://onesignal.com/api/v1/notifications"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {ONESIGNAL_REST_API_KEY}"
    }
    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "included_segments": ["All"],
        "filters": [
            {"field": "tag", "key": "destino", "relation": "=", "value": destino}
        ],
        "contents": {"en": mensaje},
        "headings": {"en": "Actualización de Estatus"}
    }
    requests.post(url, json=payload, headers=headers)

# Función para mostrar sección de administrador
def admin_panel():
    st.subheader("Panel del Administrador")

    archivo = st.file_uploader("Carga el archivo nuevo de datos", type=["xlsx"])
    if archivo:
        df_nuevo = pd.read_excel(archivo)
        st.success("Archivo cargado correctamente.")
        if st.button("Actualizar base"):
            df_hist = cargar_historico()
            cambios = detectar_cambios(df_nuevo, df_hist)
            if not cambios.empty:
                for _, row in cambios.iterrows():
                    mensaje = f"Estatus actualizado para destino {row['Destino']}: {row['Estado de atención']}"
                    enviar_notificacion(str(row['Destino']), mensaje)
                df_consolidado = pd.concat([df_hist, cambios], ignore_index=True)
                guardar_historico(df_consolidado)
                st.success(f"Base actualizada con {len(cambios)} cambios detectados.")
            else:
                st.info("No se detectaron cambios.")
    else:
        st.info("Sube un archivo Excel para comenzar.")

# Función para mostrar sección de usuario
def usuario_panel():
    st.subheader("Consulta de Pedidos")
    df_hist = cargar_historico()
    if df_hist.empty:
        st.warning("Aún no se ha cargado ningún histórico.")
        return

    destino_input = st.text_input("Escribe tu número de destino:")
    destino_filtrado = df_hist[df_hist["Destino"].astype(str).str.contains(destino_input.strip(), case=False)]

    if destino_input:
        if not destino_filtrado.empty:
            st.success(f"Se encontraron {len(destino_filtrado)} registros para el destino {destino_input}")
            st.dataframe(destino_filtrado)

            if st.button("🔔 Suscribirme a notificaciones de este destino"):
                st.markdown("✅ Te has suscrito correctamente. Recibirás notificaciones cuando el estatus cambie.")
                st.markdown("*Nota: Tu navegador debe permitir notificaciones push.*")
                st.markdown("""
                <script>
                window.OneSignal = window.OneSignal || [];
                OneSignal.push(function() {
                    OneSignal.sendTag("destino", "%s");
                });
                </script>
                """ % destino_input, unsafe_allow_html=True)
        else:
            st.warning("No se encontró ese destino en el histórico.")

# Función para mostrar login
def login_panel():
    with st.sidebar:
        st.markdown("## Acceso de Administrador")
        usuario = st.text_input("Usuario")
        contraseña = st.text_input("Contraseña", type="password")
        login = st.button("Iniciar sesión")

        if login:
            if usuario == ADMIN_USER and contraseña == ADMIN_PASS:
                st.session_state["admin"] = True
                st.experimental_rerun()
            else:
                st.error("Credenciales incorrectas")

# Función principal
def main():
    st.title("📦 Seguimiento de Pedidos Lemargo")

    if "admin" not in st.session_state:
        st.session_state["admin"] = False

    tabs = st.tabs(["🔍 Consulta", "🔐 Admin"])

    with tabs[0]:
        usuario_panel()

    with tabs[1]:
        if st.session_state["admin"]:
            admin_panel()
        else:
            login_panel()

if __name__ == "__main__":
    main()
