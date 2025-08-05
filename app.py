import streamlit as st
import pandas as pd
import numpy as np
import os
import datetime
import altair as alt
import requests
from streamlit_autorefresh import st_autorefresh
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
ONESIGNAL_APP_ID = os.getenv("ONESIGNAL_APP_ID")
ONESIGNAL_REST_API_KEY = os.getenv("ONESIGNAL_REST_API_KEY")
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")

# Configuración
st.set_page_config(page_title="Seguimiento de Pedidos", layout="wide", page_icon="📦")
st.markdown("<style>body { background-color: #0e1117; color: white; }</style>", unsafe_allow_html=True)

# ---------------------------------------------
# Funciones
# ---------------------------------------------

def cargar_datos():
    try:
        return pd.read_excel("historico_estatus.xlsx")
    except FileNotFoundError:
        st.warning("No se encontró el archivo histórico.")
        return pd.DataFrame()

def mostrar_tarjetas(resultados):
    estado_colores = {
        "Entregado": "#1f8a70",
        "En proceso": "#f39c12",
        "Cancelado": "#c0392b",
        "Pendiente": "#3498db",
        "En ruta": "#8e44ad",
        "Sin asignar": "#95a5a6"
    }

    for _, row in resultados.iterrows():
        estado = row["Estado de atención"]
        color = estado_colores.get(estado, "#2c3e50")
        with st.container():
            st.markdown(f"""
                <div style='background-color:{color}; padding: 15px; border-radius: 12px; margin-bottom: 10px;'>
                    <b>Producto:</b> {row['Producto']}<br>
                    <b>Turno:</b> {row['Turno']}<br>
                    <b>Tonel:</b> {row['Destino']}<br>
                    <b>Capacidad programada:</b> {row['Capacidad programada (Litros)']}<br>
                    <b>Fecha y hora estimada:</b> {row['Fecha y hora estimada']}<br>
                    <b>Fecha y hora de facturación:</b> {row['Fecha y hora de facturación']}<br>
                    <b>Estado de atención:</b> {estado}
                </div>
            """, unsafe_allow_html=True)

def suscribir_usuario(destino):
    player_id = st.session_state.get("player_id")
    if not player_id:
        st.warning("No se detectó tu suscripción push. Asegúrate de aceptar las notificaciones.")
        return

    tag_url = f"https://onesignal.com/api/v1/players/{player_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {ONESIGNAL_REST_API_KEY}"
    }
    data = {
        "tags": {
            f"destino_{destino}": "1"
        },
        "app_id": ONESIGNAL_APP_ID
    }
    response = requests.put(tag_url, headers=headers, json=data)
    if response.status_code == 200:
        st.success(f"✅ Te has suscrito correctamente al destino {destino}. Recibirás notificaciones si hay cambios.")
    else:
        st.error("❌ Error al suscribirse. Intenta nuevamente.")

def seccion_usuario():
    st.title("📦 Seguimiento de Pedido por Destino")
    st.markdown("Ingresa el número de destino exacto para ver el estado actual de tu pedido.")

    destino_input = st.text_input("Número de destino").strip()

    if destino_input:
        df = cargar_datos()
        if not df.empty:
            df["Destino"] = df["Destino"].astype(str)
            resultados = df[df["Destino"] == destino_input]

            if not resultados.empty:
                mostrar_tarjetas(resultados)

                # Botón de suscripción
                if st.button("🔔 Suscribirme a notificaciones de este destino"):
                    suscribir_usuario(destino_input)

                with st.expander("¿Qué ocurre si me suscribo?"):
                    st.markdown("Recibirás una notificación push en tu celular o navegador cuando el estado de tu pedido cambie.")
            else:
                st.warning("No se encontraron pedidos para ese destino.")

def seccion_admin():
    st.title("🔒 Administración")
    st.markdown("Solo personal autorizado")

    uploaded_file = st.file_uploader("Cargar nuevo archivo Excel", type=["xlsx"])
    if uploaded_file:
        try:
            nuevo_df = pd.read_excel(uploaded_file)
            historico = cargar_datos()

            nuevo_df["ID"] = nuevo_df["Destino"].astype(str) + "_" + pd.to_datetime(nuevo_df["Fecha"]).dt.strftime("%Y-%m-%d")
            historico["ID"] = historico["Destino"].astype(str) + "_" + pd.to_datetime(historico["Fecha"]).dt.strftime("%Y-%m-%d")

            df_combinado = pd.concat([historico, nuevo_df], ignore_index=True)
            df_final = df_combinado.drop_duplicates(subset="ID", keep="last")

            df_final.to_excel("historico_estatus.xlsx", index=False)
            st.success("Archivo actualizado correctamente.")
        except Exception as e:
            st.error(f"Error al procesar el archivo: {e}")

def login_panel():
    st.sidebar.markdown("## Ingreso Administrador")
    username = st.sidebar.text_input("Usuario")
    password = st.sidebar.text_input("Contraseña", type="password")
    if st.sidebar.button("Ingresar"):
        if username == ADMIN_USER and password == ADMIN_PASS:
            st.session_state["admin_logged"] = True
            st.experimental_rerun()
        else:
            st.sidebar.error("Credenciales incorrectas")
    if st.session_state.get("admin_logged"):
        seccion_admin()

def main():
    st_autorefresh(interval=0)  # No auto refresh
    st.markdown("<h2 style='color:#00adb5;'>Sistema de Seguimiento Lemargo</h2>", unsafe_allow_html=True)

    menu = st.sidebar.radio("Navegación", ["Usuario", "Administrador"], index=0)
    if menu == "Usuario":
        seccion_usuario()
    else:
        login_panel()

if __name__ == "__main__":
    main()
