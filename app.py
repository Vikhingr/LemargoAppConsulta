import streamlit as st import pandas as pd import numpy as np import os import datetime import altair as alt import requests from streamlit_autorefresh import st_autorefresh from dotenv import load_dotenv

load_dotenv()

--- Configuración general ---

st.set_page_config(page_title="Seguimiento de Pedidos", layout="wide", page_icon="📦")

--- Estilos personalizados ---

custom_css = """

<style>
body {
    background-color: #1e1e1e;
    color: white;
}
section.main > div {
    max-width: 90rem;
    padding: 2rem;
}
</style>""" st.markdown(custom_css, unsafe_allow_html=True)

--- Cargar secretos ---

ONESIGNAL_APP_ID = os.getenv("ONESIGNAL_APP_ID") ONESIGNAL_REST_API_KEY = os.getenv("ONESIGNAL_REST_API_KEY") ADMIN_USER = os.getenv("ADMIN_USER") ADMIN_PASS = os.getenv("ADMIN_PASS")

--- Funciones auxiliares ---

def cargar_datos(): try: return pd.read_excel("historico_estatus.xlsx") except FileNotFoundError: return pd.DataFrame()

def enviar_notificacion(destino): headers = { "Content-Type": "application/json", "Authorization": f"Basic {ONESIGNAL_REST_API_KEY}" } payload = { "app_id": ONESIGNAL_APP_ID, "included_segments": ["All"], "filters": [ {"field": "tag", "key": "destino", "relation": "=", "value": destino} ], "contents": {"en": f"📦 Nuevo estatus actualizado para {destino}"}, "headings": {"en": "Actualización de Pedido"} } requests.post("https://onesignal.com/api/v1/notifications", json=payload, headers=headers)

--- Sección usuario ---

def seccion_usuario(df): st.subheader("🔍 Buscar Pedido por Destino") df['ID_Destino'] = df['Destino'].astype(str).str.extract(r'^(\d+)')

numero = st.text_input("Escribe el número de destino (ej. 24806):")
destino_elegido = df[df['ID_Destino'] == numero]['Destino'].unique()

if len(destino_elegido) == 1:
    destino = destino_elegido[0]
    st.success(f"Destino detectado: {destino}")

    # Mostrar datos del destino
    df_filtrado = df[df['Destino'] == destino]
    st.dataframe(df_filtrado, use_container_width=True)

    # Gráfica
    graf = df_filtrado.groupby('Estatus')['Destino'].count().reset_index()
    chart = alt.Chart(graf).mark_bar().encode(
        x='Estatus', y='Destino', tooltip=['Estatus', 'Destino']
    ).properties(title=f"Estatus de pedidos para {destino}")
    st.altair_chart(chart, use_container_width=True)

    # Suscripción
    if st.button("🔔 Suscribirme a notificaciones de este destino"):
        js_code = f"""
        <script>
        OneSignal.push(function() {{
          OneSignal.sendTag("destino", "{destino}");
          alert("✅ Suscripción realizada. Recibirás notificaciones para el destino: {destino}");
        }});
        </script>
        """
        st.components.v1.html(js_code, height=0)
elif numero:
    st.warning("⚠️ No se encontró un destino con ese número exacto.")

--- Sección administrador ---

def seccion_admin(df): st.subheader("⚙️ Panel de Administrador") st.markdown("---")

uploaded = st.file_uploader("📤 Subir archivo nuevo (Excel)", type=[".xlsx"])
if uploaded:
    nuevo_df = pd.read_excel(uploaded)
    nuevo_df['ID'] = nuevo_df['Destino'].astype(str) + "_" + nuevo_df['Fecha'].astype(str)
    nuevo_df['Hora Consulta'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nuevo_df['Fuente'] = "admin"

    historico = cargar_datos()
    historico['ID'] = historico['Destino'].astype(str) + "_" + historico['Fecha'].astype(str)

    combinado = pd.concat([historico, nuevo_df], ignore_index=True)
    combinado = combinado.drop_duplicates(subset=['ID', 'Estatus'], keep='last')
    combinado.to_excel("historico_estatus.xlsx", index=False)

    st.success("✅ Archivo actualizado y guardado.")

    # Detectar cambios y notificar
    cambios = pd.merge(nuevo_df, historico, on='ID', suffixes=('_nuevo', '_viejo'))
    cambios = cambios[cambios['Estatus_nuevo'] != cambios['Estatus_viejo']]

    for destino_cambio in cambios['Destino_nuevo'].unique():
        enviar_notificacion(destino_cambio)

    st.info(f"🔔 Se notificó a los destinos actualizados.")

--- Login de administrador ---

def login_panel(): with st.sidebar: st.markdown("## 🔐 Acceso Administrador") user = st.text_input("Usuario") password = st.text_input("Contraseña", type="password") if st.button("Iniciar sesión"): if user == ADMIN_USER and password == ADMIN_PASS: st.session_state["admin"] = True st.experimental_rerun() else: st.error("Credenciales incorrectas")

--- Main ---

def main(): st.title("📦 Seguimiento de Pedidos por Destino") df = cargar_datos()

if "admin" not in st.session_state:
    st.session_state.admin = False

login_panel()

if st.session_state.admin:
    seccion_admin(df)
else:
    seccion_usuario(df)

--- Ejecutar ---

if name == 'main': main()

