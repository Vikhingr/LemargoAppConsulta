import streamlit as st
import pandas as pd
import os
import requests
from datetime import datetime

# ============ CONFIGURACIÓN =============
st.set_page_config(page_title="Seguimiento de Pedidos", layout="wide")

# ============ ESTILOS PERSONALIZADOS ============
st.markdown("""
    <style>
    body {background-color: #0e1117; color: #ffffff;}
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

# ============ VARIABLES DE ENTORNO ============
ONESIGNAL_APP_ID = st.secrets["ONESIGNAL_APP_ID"]
ONESIGNAL_API_KEY = st.secrets["ONESIGNAL_REST_API_KEY"]
ADMIN_USER = st.secrets["ADMIN_USER"]
ADMIN_PASS = st.secrets["ADMIN_PASS"]

# ============ FUNCIÓN DE NOTIFICACIÓN ============
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
    requests.post("https://onesignal.com/api/v1/notifications", headers=headers, json=payload)

# ============ FUNCIÓN CONSOLIDAR HISTÓRICO ============
def actualizar_historico(nuevo_df, ruta_historico="historico_estatus.xlsx"):
    nuevo_df["ID"] = nuevo_df["Destino"].astype(str) + "_" + nuevo_df["Fecha"].astype(str)
    nuevo_df["Hora Consulta"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nuevo_df["Fuente"] = "nuevo_datos.xlsx"

    if os.path.exists(ruta_historico):
        historico_df = pd.read_excel(ruta_historico)
        historico_df["ID"] = historico_df["Destino"].astype(str) + "_" + historico_df["Fecha"].astype(str)
        combinados = pd.concat([historico_df, nuevo_df], ignore_index=True)
        final = combinados.drop_duplicates(subset="ID", keep="last")
    else:
        final = nuevo_df.copy()

    final.to_excel(ruta_historico, index=False)

    # Detectar cambios en estatus
    cambios = []
    if 'historico_df' in locals():
        anteriores = historico_df.set_index("ID")["Estado de atención"]
        nuevos = nuevo_df.set_index("ID")["Estado de atención"]
        comparacion = nuevos.compare(anteriores, keep_shape=True)
        for idx in comparacion.index:
            destino = nuevo_df[nuevo_df["ID"] == idx]["Destino"].values[0]
            cambios.append(destino)
            send_push_notification(str(destino))
    return final

# ============ LOGIN DE ADMINISTRADOR ============
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

with st.sidebar:
    st.title("🔐 Admin")
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

# ============ SECCIÓN ADMIN: CARGA DE ARCHIVO ============
if st.session_state.logged_in:
    st.subheader("📤 Cargar archivo nuevo_datos.xlsx")
    archivo = st.file_uploader("Selecciona el archivo Excel", type=["xlsx"])
    if archivo:
        nuevo_df = pd.read_excel(archivo)
        columnas_requeridas = ["Destino", "Fecha", "Estado de atención", "Folio Pedido"]
        if all(col in nuevo_df.columns for col in columnas_requeridas):
            df = actualizar_historico(nuevo_df)
            st.success("✅ Archivo actualizado y consolidado al histórico.")
            st.dataframe(df.head())
        else:
            st.error("❌ El archivo no contiene las columnas necesarias.")

# ============ CONSULTA DE USUARIO ============
st.header("🔍 Consultar pedidos por destino")

if os.path.exists("historico_estatus.xlsx"):
    df = pd.read_excel("historico_estatus.xlsx")
    df["Destino"] = df["Destino"].astype(str)
else:
    df = pd.DataFrame()

destino_input = st.text_input("Escribe el número exacto del destino").strip()

if destino_input:
    resultados = df[df["Destino"] == destino_input]
    if resultados.empty:
        st.warning("⚠️ No se encontraron pedidos para ese destino.")
    else:
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

            st.markdown(f"""
                <div class="{clase}">
                    <strong>Destino:</strong> {row['Destino']}<br>
                    <strong>Folio:</strong> {row['Folio Pedido']}<br>
                    <strong>Estado:</strong> {row['Estado de atención']}<br>
                    <strong>Fecha:</strong> {row['Fecha']}<br>
                </div>
            """, unsafe_allow_html=True)

        # ========== BOTÓN DE SUSCRIPCIÓN ==========
        st.markdown(f"""
            <script src="https://cdn.onesignal.com/sdks/OneSignalSDK.js" async=""></script>
            <script>
                window.OneSignal = window.OneSignal || [];
                OneSignal.push(function() {{
                    OneSignal.init({{
                        appId: "{ONESIGNAL_APP_ID}"
                    }});
                    OneSignal.showSlidedownPrompt();
                    OneSignal.sendTag("destino", "{destino_input}");
                }});
            </script>
        """, unsafe_allow_html=True)
else:
    st.info("Escribe un número de destino para comenzar la búsqueda.")
