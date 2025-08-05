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
# Funciones corregidas
# ---------------------------------------------

def cargar_datos():
    try:
        df = pd.read_excel("historico_estatus.xlsx")
        
        # Conversión segura de tipos de datos
        df["Destino"] = df["Destino"].astype(str).str.strip()
        df["Fecha y hora estimada"] = pd.to_datetime(df["Fecha y hora estimada"], errors='coerce')
        df["Fecha y hora de facturación"] = pd.to_datetime(df["Fecha y hora de facturación"], errors='coerce')
        
        return df
    except FileNotFoundError:
        st.error("Error: El archivo 'historico_estatus.xlsx' no existe. Carga un archivo en la sección Admin.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al cargar datos: {str(e)}")
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

def seccion_usuario():
    st.title("📦 Seguimiento de Pedido por Destino")
    st.markdown("Ingresa el número de destino exacto para ver el estado actual de tu pedido.")

    destino_input = st.text_input("Número de destino").strip()

    if destino_input:
        df = cargar_datos()
        if not df.empty:
            resultados = df[df["Destino"].str.contains(destino_input, case=False, na=False)]
            
            if not resultados.empty:
                mostrar_tarjetas(resultados)
                
                if st.button("🔔 Suscribirme a notificaciones de este destino"):
                    suscribir_usuario(destino_input)
            else:
                st.warning("No se encontraron pedidos para ese destino. Verifica el número.")
        else:
            st.warning("No hay datos disponibles. Contacta al administrador.")

def seccion_admin():
    st.title("🔒 Administración")
    st.markdown("Solo personal autorizado")
    
    # Botón de cierre de sesión
    if st.button("Cerrar sesión"):
        st.session_state["admin_logged"] = False
        st.experimental_rerun()

    uploaded_file = st.file_uploader("Cargar nuevo archivo Excel", type=["xlsx"])
    if uploaded_file:
        try:
            nuevo_df = pd.read_excel(uploaded_file)
            
            # Validación básica de columnas
            columnas_requeridas = ["Destino", "Producto", "Estado de atención"]
            if not all(col in nuevo_df.columns for col in columnas_requeridas):
                st.error(f"El archivo debe contener estas columnas: {', '.join(columnas_requeridas)}")
                return
                
            # Procesamiento de datos
            nuevo_df["ID"] = nuevo_df["Destino"].astype(str) + "_" + pd.to_datetime(nuevo_df["Fecha"]).dt.strftime("%Y%m%d")
            nuevo_df["Destino"] = nuevo_df["Destino"].astype(str).str.strip()
            
            # Guardar archivo
            nuevo_df.to_excel("historico_estatus.xlsx", index=False)
            st.success("Datos actualizados correctamente!")
            st.balloons()
            
        except Exception as e:
            st.error(f"Error grave al procesar el archivo: {str(e)}")

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

def main():
    st_autorefresh(interval=0)
    st.markdown("<h2 style='color:#00adb5;'>Sistema de Seguimiento Lemargo</h2>", unsafe_allow_html=True)

    menu = st.sidebar.radio("Navegación", ["Usuario", "Administrador"], index=0)
    
    if menu == "Usuario":
        seccion_usuario()
    else:
        if st.session_state.get("admin_logged"):
            seccion_admin()
        else:
            login_panel()

if __name__ == "__main__":
    main()
