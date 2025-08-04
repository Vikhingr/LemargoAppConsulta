import streamlit as st
import pandas as pd
import os
import datetime
from io import BytesIO
import matplotlib.pyplot as plt
import requests
import altair as alt
import base64
import json

# Configuración inicial
st.set_page_config(page_title="Lemargo Pedidos", layout="wide", initial_sidebar_state="expanded")

# Estilo moderno en modo oscuro
st.markdown("""
    <style>
    body {
        background-color: #121212;
        color: #ffffff;
    }
    .stApp {
        background-color: #121212;
    }
    .css-18ni7ap.e8zbici2 {
        background-color: #1e1e1e;
    }
    .css-1cpxqw2.edgvbvh3 {
        background-color: #1e1e1e;
    }
    .stButton>button {
        background-color: #0A84FF;
        color: white;
        border-radius: 10px;
        height: 3em;
    }
    .stTextInput>div>div>input {
        background-color: #2c2c2c;
        color: white;
    }
    .stSelectbox>div>div>div>div {
        background-color: #2c2c2c;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

# Leer variables del secrets.toml
ONESIGNAL_APP_ID = st.secrets["ONESIGNAL_APP_ID"]
ONESIGNAL_REST_API_KEY = st.secrets["ONESIGNAL_REST_API_KEY"]
ADMIN_USER = st.secrets["ADMIN_USER"]
ADMIN_PASS = st.secrets["ADMIN_PASS"]

# Función para enviar notificación
def enviar_notificacion(titulo, mensaje):
    cabeceras = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {ONESIGNAL_REST_API_KEY}"
    }
    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "included_segments": ["All"],
        "headings": {"en": titulo},
        "contents": {"en": mensaje}
    }
    requests.post("https://onesignal.com/api/v1/notifications", headers=cabeceras, data=json.dumps(payload))

# Cargar archivo histórico
def cargar_historico():
    if os.path.exists("historico_estatus.xlsx"):
        return pd.read_excel("historico_estatus.xlsx")
    else:
        return pd.DataFrame()

# Guardar histórico actualizado
def guardar_historico(df):
    df.to_excel("historico_estatus.xlsx", index=False)

# Comparar y detectar cambios
def detectar_cambios(df_nuevo, df_hist):
    df_nuevo["ID"] = df_nuevo["Destino"].astype(str) + "_" + df_nuevo["Fecha"].astype(str)
    df_hist["ID"] = df_hist["Destino"].astype(str) + "_" + df_hist["Fecha"].astype(str)
    df_merged = pd.merge(df_nuevo, df_hist, on="ID", suffixes=("_nuevo", "_hist"), how="left")
    cambios = df_merged[df_merged["Estado de atención_nuevo"] != df_merged["Estado de atención_hist"]]
    return cambios

# Interfaz lateral (login)
with st.sidebar:
    st.markdown("### Acceso Admin")
    usuario = st.text_input("Usuario", value="", label_visibility="collapsed", placeholder="Usuario")
    password = st.text_input("Contraseña", type="password", label_visibility="collapsed", placeholder="Contraseña")
    entrar = st.button("Entrar")

# Validar acceso administrador
admin_autenticado = (usuario == ADMIN_USER and password == ADMIN_PASS)

if admin_autenticado:
    st.success("Acceso como Administrador ✅")
    st.header("Panel de Administración")

    archivo_cargado = st.file_uploader("Selecciona el archivo nuevo", type=["xlsx"])

    if archivo_cargado:
        st.success("Archivo cargado con éxito ✅")
        if st.button("Actualizar base"):
            df_nuevo = pd.read_excel(archivo_cargado)
            df_nuevo["Hora de consulta"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            df_nuevo["Fuente"] = "Carga admin"

            df_hist = cargar_historico()

            if not df_hist.empty:
                cambios = detectar_cambios(df_nuevo, df_hist)
                if not cambios.empty:
                    enviar_notificacion("📦 Pedido actualizado", f"{len(cambios)} pedidos cambiaron de estatus")
            else:
                cambios = df_nuevo  # primera carga

            df_final = pd.concat([df_hist, df_nuevo], ignore_index=True)
            df_final = df_final.drop_duplicates(subset=["Destino", "Fecha"], keep="last")
            guardar_historico(df_final)
            st.success("Base actualizada correctamente")

        st.info("Después de subir el archivo, da clic en **Actualizar base**.")
else:
    # Modo usuario
    st.header("Consulta de pedidos por destino")
    df_hist = cargar_historico()

    if df_hist.empty:
        st.warning("Aún no hay datos disponibles. El administrador debe cargar el archivo.")
    else:
        destinos = sorted(df_hist["Destino"].unique())
        destino_seleccionado = st.selectbox("Selecciona tu destino", destinos)

        df_destino = df_hist[df_hist["Destino"] == destino_seleccionado]

        if not df_destino.empty:
            st.subheader("Historial del destino seleccionado")
            st.dataframe(df_destino.sort_values("Fecha", ascending=False), use_container_width=True)

            # Gráfica por estatus
            st.subheader("Gráfica de estatus en el tiempo")
            fig, ax = plt.subplots(figsize=(10, 4))
            try:
                df_graf = df_destino.groupby("Fecha")["Estado de atención"].value_counts().unstack().fillna(0)
                df_graf.plot(kind="bar", stacked=True, ax=ax)
                ax.set_ylabel("Pedidos")
                ax.set_xlabel("Fecha")
                st.pyplot(fig)
            except:
                st.info("No hay datos suficientes para graficar.")

            # Exportar
            output = BytesIO()
            df_destino.to_excel(output, index=False)
            b64 = base64.b64encode(output.getvalue()).decode()
            href = f'<a href="data:application/octet-stream;base64,{b64}" download="reporte_destino.xlsx">📥 Descargar reporte</a>'
            st.markdown(href, unsafe_allow_html=True)
        else:
            st.warning("No se encontraron datos para el destino seleccionado.")
