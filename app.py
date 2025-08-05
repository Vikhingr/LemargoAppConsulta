import streamlit as st
import pandas as pd
import numpy as np
import os
import datetime
from streamlit_autorefresh import st_autorefresh
import requests
from dotenv import load_dotenv

load_dotenv()

# Configuración de página
st.set_page_config(page_title="Seguimiento de Pedidos", layout="wide")

# Estilo visual personalizado
st.markdown("""
    <style>
    body, .stApp {
        background-color: #0e1117;
        color: #ffffff;
    }
    .card {
        background-color: #1f2937;
        padding: 1rem;
        border-radius: 12px;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.5);
        margin-bottom: 1.2rem;
        border-left: 6px solid #6b7280;
    }
    .card h4 {
        margin-top: 0;
        font-size: 1.2rem;
        color: #ffffff;
    }
    .card p {
        margin: 0.2rem 0;
        font-size: 0.95rem;
    }
    </style>
""", unsafe_allow_html=True)

# Variables de entorno
ONESIGNAL_APP_ID = os.getenv("ONESIGNAL_APP_ID")
ONESIGNAL_REST_API_KEY = os.getenv("ONESIGNAL_REST_API_KEY")
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")

# Variables de archivo
ARCHIVO_ACTUAL = "nuevo_datos.xlsx"
ARCHIVO_HISTORICO = "historico_estatus.xlsx"

# Función para detectar cambios en el archivo
def detectar_cambios(df_actual, df_historico):
    df_actual["ID"] = df_actual["Destino"].astype(str) + "_" + df_actual["Fecha"].astype(str)
    df_historico["ID"] = df_historico["Destino"].astype(str) + "_" + df_historico["Fecha"].astype(str)

    df_merged = pd.merge(df_actual, df_historico, on="ID", how="left", suffixes=("", "_hist"))
    cambios = df_merged[df_merged["Estado de atención"] != df_merged["Estado de atención_hist"]]
    return cambios["ID"].tolist()

# Función para enviar notificaciones push
def enviar_notificacion(destino, mensaje):
    if not ONESIGNAL_APP_ID or not ONESIGNAL_REST_API_KEY:
        print("Faltan claves de OneSignal.")
        return

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Basic {ONESIGNAL_REST_API_KEY}"
    }
    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "filters": [
            {"field": "tag", "key": "destino", "relation": "=", "value": str(destino)}
        ],
        "contents": {"en": mensaje},
        "headings": {"en": f"📦 Pedido actualizado ({destino})"},
        "ios_sound": "default",
        "android_sound": "default"
    }

    try:
        response = requests.post("https://onesignal.com/api/v1/notifications", headers=headers, json=payload)
        print("Notificación enviada:", response.status_code)
    except Exception as e:
        print("Error al enviar notificación:", e)

# Función para mostrar tarjetas visuales
def mostrar_tarjetas(df_filtrado):
    estado_colores = {
        "Programado": "#2563eb",   # Azul
        "Cargando": "#facc15",     # Amarillo
        "Facturado": "#22c55e",    # Verde
    }

    for _, row in df_filtrado.iterrows():
        estado = str(row['Estado de atención'])
        color = "#ef4444" if "cancelado" in estado.lower() else estado_colores.get(estado, "#6b7280")

        st.markdown(f"""
            <div class="card" style="border-left: 6px solid {color};">
                <h4>🧪 <strong>{row['Producto']}</strong></h4>
                <p>👷‍♂️ <strong>Turno:</strong> {row['Turno']}</p>
                <p>🛢️ <strong>Tonel:</strong> {row['Tonel']}</p>
                <p>🧴 <strong>Capacidad:</strong> {row['Capacidad programada (Litros)']} L</p>
                <p>📅 <strong>Fecha estimada:</strong> {row['Fecha y hora estimada']}</p>
                <p>🧾 <strong>Fecha facturación:</strong> {row['Fecha y hora de facturación']}</p>
                <p>📌 <strong>Estado:</strong> <span style="color:{color};"><strong>{estado}</strong></span></p>
            </div>
        """, unsafe_allow_html=True)

# Función para procesar datos nuevos
def actualizar_historico():
    if not os.path.exists(ARCHIVO_ACTUAL):
        st.warning("⚠️ No se encontró el archivo nuevo_datos.xlsx")
        return

    df_nuevo = pd.read_excel(ARCHIVO_ACTUAL)
    df_nuevo["Fecha"] = pd.to_datetime(df_nuevo["Fecha"], errors='coerce').dt.date
    df_nuevo["Hora consulta"] = datetime.datetime.now()
    df_nuevo["Fuente"] = "nuevo_datos.xlsx"

    if os.path.exists(ARCHIVO_HISTORICO):
        df_hist = pd.read_excel(ARCHIVO_HISTORICO)
        cambios = detectar_cambios(df_nuevo, df_hist)
        for id_cambio in cambios:
            destino = id_cambio.split("_")[0]
            enviar_notificacion(destino, f"🆕 Pedido actualizado para destino {destino}.")
        df_concat = pd.concat([df_hist, df_nuevo])
        df_final = df_concat.drop_duplicates(subset=["Destino", "Fecha"], keep="last")
    else:
        df_final = df_nuevo

    df_final.to_excel(ARCHIVO_HISTORICO, index=False)
    st.success("✅ Base actualizada con éxito.")

# Panel de administración
def login_panel():
    with st.sidebar:
        st.header("🔐 Acceso Admin")
        usuario = st.text_input("Usuario")
        contraseña = st.text_input("Contraseña", type="password")
        if st.button("Iniciar sesión"):
            if usuario == ADMIN_USER and contraseña == ADMIN_PASS:
                st.session_state["admin"] = True
                st.experimental_rerun()
            else:
                st.error("Credenciales incorrectas.")

# Interfaz principal de usuario
def interfaz_usuario():
    st.title("📦 Seguimiento de Pedidos")

    if not os.path.exists(ARCHIVO_HISTORICO):
        st.warning("⚠️ Aún no se ha cargado información.")
        return

    df = pd.read_excel(ARCHIVO_HISTORICO)
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors='coerce').dt.date
    df["Destino"] = df["Destino"].astype(str)

    busqueda = st.text_input("🔍 Ingresa el número de tu destino").strip()

    if busqueda:
        df_filtrado = df[df["Destino"].str.contains(busqueda, case=False, na=False)]

        if not df_filtrado.empty:
            mostrar_tarjetas(df_filtrado.sort_values(by="Fecha", ascending=False))
        else:
            st.info("❌ No se encontraron pedidos para ese destino.")
    else:
        st.info("👈 Ingresa el número de tu destino para ver tus pedidos.")

# Panel admin: subir archivo
def panel_admin():
    st.title("⚙️ Panel de Administración")
    st.info("Desde aquí puedes subir un nuevo archivo de pedidos.")

    archivo = st.file_uploader("📤 Subir archivo Excel", type=["xlsx"])

    if archivo:
        with open(ARCHIVO_ACTUAL, "wb") as f:
            f.write(archivo.read())
        actualizar_historico()

# Main
def main():
    if "admin" not in st.session_state:
        st.session_state["admin"] = False

    if st.session_state["admin"]:
        panel_admin()
    else:
        interfaz_usuario()
        login_panel()

if __name__ == "__main__":
    main()
