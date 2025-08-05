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
# Funciones mejoradas
# ---------------------------------------------

def cargar_datos():
    """Carga los datos del archivo Excel con manejo robusto de errores"""
    try:
        df = pd.read_excel("historico_estatus.xlsx")
        
        # Conversión segura de tipos de datos y limpieza
        df["Destino"] = df["Destino"].astype(str).str.strip()
        df["Fecha y hora estimada"] = pd.to_datetime(df["Fecha y hora estimada"], errors='coerce')
        df["Fecha y hora de facturación"] = pd.to_datetime(df["Fecha y hora de facturación"], errors='coerce')
        
        # Verificar columnas esenciales
        columnas_requeridas = ["Destino", "Producto", "Estado de atención", "Capacidad programada (Litros)"]
        for col in columnas_requeridas:
            if col not in df.columns:
                raise ValueError(f"Columna requerida faltante: {col}")
        
        return df
    except FileNotFoundError:
        st.error("Error: No se encontró el archivo 'historico_estatus.xlsx'. Por favor, carga un archivo en la sección Admin.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error crítico al cargar datos: {str(e)}")
        return pd.DataFrame()

def mostrar_tarjetas(resultados):
    """Muestra los resultados en tarjetas visuales con colores por estado"""
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
    """Gestiona la suscripción a notificaciones push"""
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
    
    try:
        response = requests.put(tag_url, headers=headers, json=data)
        if response.status_code == 200:
            st.success(f"✅ Te has suscrito correctamente al destino {destino}. Recibirás notificaciones si hay cambios.")
        else:
            st.error(f"❌ Error al suscribirse. Código de error: {response.status_code}")
    except Exception as e:
        st.error(f"❌ Error de conexión: {str(e)}")

def seccion_usuario():
    """Interfaz para usuarios regulares"""
    st.title("📦 Seguimiento de Pedido por Destino")
    st.markdown("Ingresa el número de destino exacto para ver el estado actual de tu pedido.")

    destino_input = st.text_input("Número de destino", key="busqueda_destino").strip()

    if destino_input:
        df = cargar_datos()
        if not df.empty:
            # Búsqueda más flexible (contiene el texto ingresado)
            resultados = df[df["Destino"].str.contains(destino_input, case=False, na=False)]
            
            if not resultados.empty:
                st.success(f"🔍 Se encontraron {len(resultados)} pedidos para el destino {destino_input}")
                mostrar_tarjetas(resultados)
                
                if st.button("🔔 Suscribirme a notificaciones de este destino"):
                    suscribir_usuario(destino_input)
            else:
                st.warning("No se encontraron pedidos para ese destino. Verifica el número.")
        else:
            st.warning("No hay datos disponibles. Contacta al administrador.")

def seccion_admin():
    """Panel de administración mejorado"""
    st.title("🔒 Panel de Administración")
    
    # Barra de herramientas superior
    with st.container():
        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button("🚪 Cerrar sesión", type="primary"):
                st.session_state["admin_logged"] = False
                st.rerun()
    
    st.subheader("Cargar nuevos datos")
    uploaded_file = st.file_uploader("Selecciona un archivo Excel", type=["xlsx"], key="file_uploader")
    
    if uploaded_file:
        try:
            nuevo_df = pd.read_excel(uploaded_file)
            
            # Validación de columnas
            columnas_requeridas = ["Destino", "Producto", "Estado de atención", "Fecha"]
            faltantes = [col for col in columnas_requeridas if col not in nuevo_df.columns]
            
            if faltantes:
                st.error(f"El archivo no contiene las columnas requeridas: {', '.join(faltantes)}")
                return
            
            # Procesamiento de datos
            nuevo_df["ID"] = nuevo_df["Destino"].astype(str) + "_" + pd.to_datetime(nuevo_df["Fecha"]).dt.strftime("%Y%m%d")
            nuevo_df["Destino"] = nuevo_df["Destino"].astype(str).str.strip()
            
            # Guardar archivo
            nuevo_df.to_excel("historico_estatus.xlsx", index=False)
            
            st.success("✅ Datos actualizados correctamente!")
            st.balloons()
            
            # Mostrar vista previa
            with st.expander("🔍 Vista previa de los datos cargados"):
                st.dataframe(nuevo_df.head(10))
                
        except Exception as e:
            st.error(f"❌ Error al procesar el archivo: {str(e)}")
    
    # Estadísticas rápidas
    if os.path.exists("historico_estatus.xlsx"):
        st.subheader("📊 Estadísticas actuales")
        df = cargar_datos()
        if not df.empty:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total pedidos", len(df))
            with col2:
                st.metric("Pedidos entregados", len(df[df["Estado de atención"] == "Entregado"]))
            with col3:
                st.metric("Pedidos pendientes", len(df[df["Estado de atención"] == "Pendiente"]))

def login_panel():
    """Formulario de login mejorado"""
    st.title("🔐 Autenticación requerida")
    
    with st.form("login_form"):
        username = st.text_input("Usuario", key="username_input")
        password = st.text_input("Contraseña", type="password", key="password_input")
        
        if st.form_submit_button("Ingresar", type="primary"):
            if username == ADMIN_USER and password == ADMIN_PASS:
                st.session_state["admin_logged"] = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas. Intenta nuevamente.")

def main():
    """Función principal con gestión mejorada de estado"""
    st_autorefresh(interval=0)
    
    # Inicialización de estado
    if "admin_logged" not in st.session_state:
        st.session_state["admin_logged"] = False
    
    st.markdown("<h2 style='color:#00adb5;'>Sistema de Seguimiento Lemargo</h2>", unsafe_allow_html=True)
    
    # Menú de navegación
    menu = st.sidebar.radio("Navegación", ["Usuario", "Administrador"], index=0)
    
    if menu == "Usuario":
        seccion_usuario()
    else:
        if st.session_state["admin_logged"]:
            seccion_admin()
        else:
            login_panel()

if __name__ == "__main__":
    main()
