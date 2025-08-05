import streamlit as st
import pandas as pd
import numpy as np
import os
import datetime
import altair as alt
import requests
from streamlit_autorefresh import st_autorefresh
from dotenv import load_dotenv

load_dotenv()

# Configuración de página
st.set_page_config(page_title="Seguimiento de Pedidos", layout="wide", initial_sidebar_state="collapsed")

# Variables de entorno (desde secrets o .env)
ONESIGNAL_APP_ID = st.secrets.get("ONESIGNAL_APP_ID", os.getenv("ONESIGNAL_APP_ID"))
ONESIGNAL_REST_API_KEY = st.secrets.get("ONESIGNAL_REST_API_KEY", os.getenv("ONESIGNAL_REST_API_KEY"))
ADMIN_USER = st.secrets.get("ADMIN_USER", os.getenv("ADMIN_USER"))
ADMIN_PASS = st.secrets.get("ADMIN_PASS", os.getenv("ADMIN_PASS"))

# Archivos clave
HISTORICO_PATH = "historico_estatus.xlsx"
NUEVO_PATH = "nuevo_datos.xlsx"

# Función para enviar notificación push
def enviar_notificacion(destino):
    url = "https://onesignal.com/api/v1/notifications"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Basic {ONESIGNAL_REST_API_KEY}"
    }
    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "included_segments": ["All"],
        "filters": [{"field": "tag", "key": "destino", "relation": "=", "value": destino}],
        "contents": {"en": f"📦 Nuevo estatus disponible para el destino {destino}"},
        "headings": {"en": "Actualización de Pedido"},
        "url": "https://prueba-ec7n9gexkqvdoh8aqv2k2r.streamlit.app/"
    }
    requests.post(url, json=payload, headers=headers)

# Carga segura de datos
@st.cache_data(ttl=60)
def cargar_datos(path):
    return pd.read_excel(path)

# Función de suscripción OneSignal
def script_suscripcion(destino):
    return f"""
    <script>
      window.OneSignal = window.OneSignal || [];
      OneSignal.push(function() {{
        OneSignal.sendTag("destino", "{destino}");
        alert("🔔 Suscripción activada para destino {destino}");
      }});
    </script>
    """

# Interfaz de usuario final
def panel_usuario():
    st.markdown("## 📦 Consulta tu pedido por destino")
    destino_input = st.text_input("🔎 Ingresa el número de destino exacto:", key="destino_search")

    if destino_input:
        df = cargar_datos(HISTORICO_PATH)
        df = df[df["Destino"].astype(str) == destino_input]

        if not df.empty:
            st.components.v1.html(script_suscripcion(destino_input), height=0)

            st.markdown("### ✅ Últimos pedidos encontrados")
            columnas_mostrar = [
                "Producto",
                "Turno",
                "Tonel",
                "Capacidad programada (Litros)",
                "Fecha y hora estimada",
                "Fecha y hora de facturación",
                "Estado de atención"
            ]

            for _, row in df.iterrows():
                with st.container():
                    st.markdown("---")
                    for col in columnas_mostrar:
                        valor = row[col]
                        st.markdown(f"**{col}:** {valor}")
        else:
            st.warning("⚠️ No se encontraron registros para ese destino.")

# Panel de login admin
def login_panel():
    with st.sidebar:
        st.markdown("## 🔐 Acceso Administrador")
        user = st.text_input("Usuario")
        passwd = st.text_input("Contraseña", type="password")
        login_btn = st.button("Iniciar sesión")

    if login_btn and user == ADMIN_USER and passwd == ADMIN_PASS:
        st.session_state["admin"] = True
        st.experimental_rerun()
    elif login_btn:
        st.error("❌ Credenciales incorrectas")

# Panel administrador
def panel_admin():
    st.markdown("## 🛠️ Panel Administrador")
    archivo = st.file_uploader("📤 Cargar archivo nuevo_datos.xlsx", type=["xlsx"])

    if archivo:
        df_nuevo = pd.read_excel(archivo)
        df_nuevo.to_excel(NUEVO_PATH, index=False)
        st.success("✅ Archivo cargado correctamente.")

        if st.button("🔄 Actualizar Base"):
            if os.path.exists(HISTORICO_PATH):
                df_historico = pd.read_excel(HISTORICO_PATH)
            else:
                df_historico = pd.DataFrame()

            df_nuevo["ID"] = df_nuevo["Destino"].astype(str) + "_" + df_nuevo["Fecha"].astype(str)
            df_historico["ID"] = df_historico["Destino"].astype(str) + "_" + df_historico["Fecha"].astype(str)

            df_merge = df_nuevo.merge(df_historico[["ID", "Estado de atención"]], on="ID", how="left", suffixes=("", "_anterior"))
            df_cambios = df_merge[df_merge["Estado de atención"] != df_merge["Estado de atención_anterior"]]

            if not df_cambios.empty:
                for destino in df_cambios["Destino"].unique():
                    enviar_notificacion(str(destino))
                st.success(f"📣 {len(df_cambios)} cambios detectados. Notificaciones enviadas.")
            else:
                st.info("ℹ️ No hubo cambios en el estatus.")

            df_nuevo["Hora de actualización"] = datetime.datetime.now()
            df_nuevo.to_excel(HISTORICO_PATH, index=False)
            st.success("📚 Histórico actualizado.")
        else:
            st.info("Haz clic en 'Actualizar Base' para procesar cambios.")

# Inicio
def main():
    st.title("📦 Seguimiento de Pedidos - Lemargo")

    if "admin" not in st.session_state:
        st.session_state["admin"] = False

    menu = ["Usuario", "Administrador"]
    opcion = st.sidebar.selectbox("Navegación", menu)

    if opcion == "Usuario":
        panel_usuario()
    elif opcion == "Administrador":
        if st.session_state["admin"]:
            panel_admin()
        else:
            login_panel()

if __name__ == "__main__":
    main()
