import streamlit as st
import pandas as pd
import numpy as np
import os
import datetime
import altair as alt
import requests
from streamlit_autorefresh import st_autorefresh
from dotenv import load_dotenv

# Cargar variables del entorno
load_dotenv()
ONESIGNAL_APP_ID = os.getenv("ONESIGNAL_APP_ID")
ONESIGNAL_REST_API_KEY = os.getenv("ONESIGNAL_REST_API_KEY")
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")

st.set_page_config(page_title="Seguimiento de pedidos", layout="wide", page_icon="🚛")

# Estilo
st.markdown("""
<style>
body {background-color: #0E1117;}
[data-testid="stSidebar"] {background-color: #1E1E1E;}
.card {
    background-color: #262730;
    padding: 1rem;
    border-radius: 1rem;
    margin-bottom: 1rem;
    color: white;
}
.cancelado {border-left: 6px solid red;}
.entregado {border-left: 6px solid green;}
.enproceso {border-left: 6px solid orange;}
</style>
""", unsafe_allow_html=True)

# ---------------- FUNCIONES ----------------

def cargar_datos():
    if os.path.exists("nuevo_datos.xlsx"):
        nuevo = pd.read_excel("nuevo_datos.xlsx")
        nuevo["ID"] = nuevo["Destino"].astype(str) + "_" + pd.to_datetime(nuevo["Fecha"]).dt.strftime('%Y-%m-%d')
        nuevo["Hora consulta"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        nuevo["Fuente"] = "nuevo_datos"

        if os.path.exists("historico_estatus.xlsx"):
            historico = pd.read_excel("historico_estatus.xlsx")
            historico = pd.concat([historico, nuevo], ignore_index=True)
            historico.drop_duplicates(subset=["ID", "Estado de atención"], keep='last', inplace=True)
        else:
            historico = nuevo.copy()

        historico.to_excel("historico_estatus.xlsx", index=False)
        return nuevo, historico
    elif os.path.exists("historico_estatus.xlsx"):
        historico = pd.read_excel("historico_estatus.xlsx")
        return pd.DataFrame(), historico
    else:
        return pd.DataFrame(), pd.DataFrame()

def enviar_notificacion(destino):
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Basic {ONESIGNAL_REST_API_KEY}",
    }
    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "included_segments": ["Subscribed Users"],
        "filters": [
            {"field": "tag", "key": "destino", "relation": "=", "value": str(destino)}
        ],
        "contents": {"en": f"📦 Nuevos estatus para el destino {destino}"},
        "headings": {"en": "Actualización de pedidos"},
    }
    requests.post("https://onesignal.com/api/v1/notifications", headers=headers, json=payload)

def tarjeta(pedido):
    estatus = pedido["Estado de atención"].lower()
    clase = "cancelado" if "cancel" in estatus else "entregado" if "entregado" in estatus else "enproceso"
    st.markdown(f"""
    <div class="card {clase}">
        <strong>🧾 Producto:</strong> {pedido["Producto"]}<br>
        <strong>🕐 Turno:</strong> {pedido["Turno"]}<br>
        <strong>🛢️ Tonel:</strong> {pedido["Clave"]}<br>
        <strong>🚚 Capacidad:</strong> {pedido["Capacidad programada (Litros)"]}<br>
        <strong>⏱️ Fecha estimada:</strong> {pedido["Fecha y hora estimada"]}<br>
        <strong>📄 Facturado:</strong> {pedido["Fecha y hora de facturación"]}<br>
        <strong>📌 Estatus:</strong> {pedido["Estado de atención"]}
    </div>
    """, unsafe_allow_html=True)

# ---------------- INTERFAZ ----------------

st.title("🚛 Seguimiento de pedidos por destino")

nuevo, historico = cargar_datos()

# Campo para el número de destino exacto
destino_input = st.text_input("🔎 Ingresa el número de destino (ej. 58):", "")

# Botón para suscripción a notificaciones
if destino_input:
    st.info("🔔 Al suscribirte, recibirás notificaciones push cuando cambie el estatus de este destino.")
    if st.button("✅ Suscribirme a notificaciones de este destino"):
        st.markdown(f"""
        <script>
            window.OneSignal = window.OneSignal || [];
            OneSignal.push(function() {{
                OneSignal.sendTag("destino", "{destino_input}");
                alert("Te has suscrito a las notificaciones del destino {destino_input}");
            }});
        </script>
        """, unsafe_allow_html=True)

# Filtrar y mostrar
if destino_input and not historico.empty:
    resultados = historico[historico["Destino"].astype(str) == destino_input]

    if not resultados.empty:
        st.success(f"📦 {len(resultados)} pedido(s) encontrados para el destino {destino_input}")
        for _, row in resultados.iterrows():
            tarjeta(row)
    else:
        st.warning("❌ No se encontraron pedidos con ese número exacto de destino.")
elif not destino_input:
    st.info("🔎 Por favor ingresa un número de destino para comenzar.")
