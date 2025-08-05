import streamlit as st
import pandas as pd
import os
from datetime import datetime
import pytz
import hashlib
import json
import requests

st.set_page_config(page_title="Consulta Pedidos Lemargo", layout="wide", initial_sidebar_state="collapsed")

# ---------- FUNCIONES AUXILIARES ----------

def cargar_datos_historico():
    if os.path.exists("historico_estatus.xlsx"):
        return pd.read_excel("historico_estatus.xlsx")
    else:
        return pd.DataFrame()

def cargar_datos_nuevos():
    if os.path.exists("nuevo_datos.xlsx"):
        return pd.read_excel("nuevo_datos.xlsx")
    else:
        return None

def guardar_historico(df):
    df.to_excel("historico_estatus.xlsx", index=False)

def detectar_cambios(df_nuevo, df_hist):
    df_nuevo["ID"] = df_nuevo["Destino"].astype(str) + "_" + df_nuevo["Fecha"].astype(str)
    df_hist["ID"] = df_hist["Destino"].astype(str) + "_" + df_hist["Fecha"].astype(str)

    df_merge = pd.merge(df_nuevo, df_hist, on="ID", suffixes=("_nuevo", "_hist"), how="left")
    df_cambios = df_merge[df_merge["Estado de atención_nuevo"] != df_merge["Estado de atención_hist"]]
    
    if not df_cambios.empty:
        df_cambios = df_cambios[df_nuevo.columns]
    
    return df_cambios

def enviar_notificacion(title, message):
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Basic {st.secrets['ONESIGNAL_REST_API_KEY']}"
    }

    payload = {
        "app_id": st.secrets["ONESIGNAL_APP_ID"],
        "included_segments": ["All"],
        "headings": {"en": title},
        "contents": {"en": message},
        "data": {"tipo": "cambio_estado"},
        "ttl": 60,
        "priority": 10
    }

    requests.post("https://onesignal.com/api/v1/notifications", headers=headers, json=payload)

def actualizar_base():
    df_hist = cargar_datos_historico()
    df_nuevo = cargar_datos_nuevos()

    if df_nuevo is None:
        st.warning("⚠️ No se encontró el archivo 'nuevo_datos.xlsx'.")
        return

    cambios = detectar_cambios(df_nuevo, df_hist)
    
    if not cambios.empty:
        for _, row in cambios.iterrows():
            enviar_notificacion("📦 Pedido actualizado", f"{row['Destino']} cambió a '{row['Estado de atención']}'")
    
    df_nuevo["Fecha Consulta"] = datetime.now(pytz.timezone("America/Mexico_City")).strftime("%Y-%m-%d %H:%M:%S")
    df_nuevo["Fuente"] = "nuevo_datos.xlsx"

    df_final = pd.concat([df_hist, df_nuevo]).drop_duplicates(subset=["Destino", "Fecha"], keep="last")
    guardar_historico(df_final)

    st.success("✅ Base actualizada correctamente")

# ---------- LOGIN PANEL ----------

def login_panel():
    if not st.session_state.get("logged_in"):
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("## 👤 Iniciar sesión como administrador")
            user = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")

            if st.button("Iniciar sesión"):
                if user == st.secrets["ADMIN_USER"] and password == st.secrets["ADMIN_PASS"]:
                    st.session_state["logged_in"] = True
                    st.experimental_rerun()
                else:
                    st.error("Credenciales incorrectas")
        st.stop()

# ---------- INTERFAZ ADMIN ----------

def admin_panel():
    login_panel()
    st.title("Panel de Administración 🔐")
    
    if st.button("📥 Actualizar Base"):
        actualizar_base()

    df_hist = cargar_datos_historico()
    st.dataframe(df_hist)

# ---------- INTERFAZ USUARIO ----------

def usuario_panel():
    st.title("Consulta de Pedidos 📦")

    df_hist = cargar_datos_historico()
    if df_hist.empty:
        st.warning("⚠️ No hay datos históricos cargados.")
        return

    destino_opciones = df_hist["Destino"].dropna().unique().tolist()
    destino = st.selectbox("Selecciona tu destino:", sorted(destino_opciones))

    fecha = st.date_input("Filtrar por fecha (opcional):", value=None)

    df_filtrado = df_hist[df_hist["Destino"] == destino]
    if fecha:
        df_filtrado = df_filtrado[df_filtrado["Fecha"] == pd.to_datetime(fecha)]

    columnas_a_mostrar = [
        "Fecha", "Estado de atención", "Folio Pedido", "Producto",
        "Presentación", "Turno", "Transportista", "Fecha y hora estimada"
    ]

    df_filtrado = df_filtrado[columnas_a_mostrar]
    st.dataframe(df_filtrado)

# ---------- MAIN ----------

def main():
    st.markdown("<h1 style='text-align: center;'>🛢️ Lemargo - Estado de Pedidos</h1>", unsafe_allow_html=True)

    menu = st.selectbox("Navegar:", ["Usuario", "Admin"])

    if menu == "Admin":
        admin_panel()
    else:
        usuario_panel()

if __name__ == "__main__":
    main()
