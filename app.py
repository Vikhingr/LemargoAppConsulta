import streamlit as st
import pandas as pd
import os
from datetime import datetime
import matplotlib.pyplot as plt
from io import BytesIO
import requests
import json

# OneSignal config desde secrets.toml
ONESIGNAL_APP_ID = st.secrets["ONESIGNAL_APP_ID"]
ONESIGNAL_REST_API_KEY = st.secrets["ONESIGNAL_REST_API_KEY"]

# Estilos modernos (modo oscuro)
st.set_page_config(page_title="Seguimiento de Pedidos", layout="wide")
hide_st_style = """
    <style>
    body { background-color: #0e1117; color: white; }
    .stApp { background-color: #0e1117; }
    .css-1d391kg { background-color: #1e222d; }
    .css-1v0mbdj, .css-1d391kg, .css-1c7y2kd { border: none !important; }
    </style>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)

# Archivos
HISTORICO_PATH = "historico_estatus.xlsx"
NUEVO_PATH = "nuevos_datos.xlsx"

# Crear histórico si no existe
if not os.path.exists(HISTORICO_PATH):
    pd.DataFrame(columns=[
        'Fecha', 'Folio Pedido', 'Centro de entrega', 'Destino', 'Producto',
        'Presentación', 'Turno', 'Medio', 'Clave', 'Transportista',
        'Capacidad programada (Litros)', 'Fecha y hora estimada',
        'Fecha y hora de facturación', 'Estado de atención',
        'Fecha Actualización', 'Hora Actualización', 'Fuente',
        'Estatus Anterior', 'Estatus Actual'
    ]).to_excel(HISTORICO_PATH, index=False)

# Función para enviar notificación
def enviar_notificacion(destino, mensaje):
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Basic {ONESIGNAL_REST_API_KEY}"
    }
    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "included_segments": ["Subscribed Users"],
        "filters": [{"field": "tag", "key": "destino", "relation": "=", "value": destino}],
        "headings": {"en": "Actualización de pedido"},
        "contents": {"en": mensaje}
    }
    requests.post("https://onesignal.com/api/v1/notifications", headers=headers, json=payload)

# Función para comparar archivos y actualizar histórico
def actualizar_historico():
    if not os.path.exists(NUEVO_PATH):
        st.warning("No se encontró el archivo nuevos_datos.xlsx")
        return pd.read_excel(HISTORICO_PATH)

    nuevo = pd.read_excel(NUEVO_PATH)
    historico = pd.read_excel(HISTORICO_PATH)

    ahora = datetime.now()
    fecha = ahora.date().strftime("%Y-%m-%d")
    hora = ahora.strftime("%H:%M:%S")

    cambios = []
    for _, fila in nuevo.iterrows():
        clave = f"{fila['Destino']}_{fila['Fecha']}"
        match = historico[
            (historico['Destino'] == fila['Destino']) &
            (historico['Fecha'] == fila['Fecha'])
        ]
        if match.empty:
            fila_h = fila.copy()
            fila_h["Fecha Actualización"] = fecha
            fila_h["Hora Actualización"] = hora
            fila_h["Fuente"] = "Carga Nueva"
            fila_h["Estatus Anterior"] = ""
            fila_h["Estatus Actual"] = fila['Estado de atención']
            historico = historico.append(fila_h, ignore_index=True)
        else:
            estatus_ant = match.iloc[-1]["Estado de atención"]
            if estatus_ant != fila['Estado de atención']:
                fila_h = fila.copy()
                fila_h["Fecha Actualización"] = fecha
                fila_h["Hora Actualización"] = hora
                fila_h["Fuente"] = "Cambio"
                fila_h["Estatus Anterior"] = estatus_ant
                fila_h["Estatus Actual"] = fila['Estado de atención']
                historico = historico.append(fila_h, ignore_index=True)
                cambios.append((fila['Destino'], f"Pedido actualizado: {estatus_ant} → {fila['Estado de atención']}"))

    if cambios:
        for destino, mensaje in cambios:
            enviar_notificacion(destino, mensaje)

    historico.to_excel(HISTORICO_PATH, index=False)
    return historico

# Interfaz de login discreta
col1, col2 = st.columns([1, 4])
with col1:
    st.markdown("### Admin Login")
    with st.form("login_form"):
        username = st.text_input("Usuario", type="default")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Entrar")

    is_admin = False
    if submit:
        if username == st.secrets["ADMIN_USER"] and password == st.secrets["ADMIN_PASS"]:
            is_admin = True
        else:
            st.error("Credenciales incorrectas")

with col2:
    st.title("📦 Seguimiento de Pedidos")

    df = actualizar_historico()

    if is_admin:
        st.success("Modo administrador")

        with st.expander("📁 Subir archivo nuevos_datos.xlsx"):
            archivo = st.file_uploader("Subir archivo Excel", type="xlsx")
            if archivo:
                with open(NUEVO_PATH, "wb") as f:
                    f.write(archivo.read())
                st.success("Archivo cargado, se actualizará automáticamente al recargar.")

        with st.expander("📊 Ver datos históricos"):
            st.dataframe(df)

        with st.expander("📤 Exportar por destino o fecha"):
            col_f1, col_f2 = st.columns(2)
            destino_f = col_f1.text_input("Destino")
            fecha_f = col_f2.date_input("Fecha")

            df_filtrado = df.copy()
            if destino_f:
                df_filtrado = df_filtrado[df_filtrado['Destino'].str.contains(destino_f, case=False)]
            if fecha_f:
                df_filtrado = df_filtrado[df_filtrado['Fecha'] == pd.to_datetime(fecha_f)]

            st.dataframe(df_filtrado)

            def convertir_excel(df):
                buffer = BytesIO()
                df.to_excel(buffer, index=False)
                buffer.seek(0)
                return buffer

            st.download_button("Descargar Excel", convertir_excel(df_filtrado), file_name="reporte_filtrado.xlsx")

    else:
        with st.expander("🔎 Consulta por destino y fecha"):
            destino_u = st.text_input("Destino")
            fecha_u = st.date_input("Fecha del pedido")
            df_user = df.copy()
            if destino_u:
                df_user = df_user[df_user['Destino'].str.contains(destino_u, case=False)]
            if fecha_u:
                df_user = df_user[df_user['Fecha'] == pd.to_datetime(fecha_u)]

            st.dataframe(df_user)

            if not df_user.empty:
                st.markdown("#### Evolución del estatus")
                fig, ax = plt.subplots()
                df_user.groupby('Fecha Actualización')['Estado de atención'].last().plot(marker='o', ax=ax)
                ax.set_ylabel("Estatus")
                ax.set_xlabel("Fecha")
                ax.grid(True)
                st.pyplot(fig)
