import streamlit as st
import pandas as pd
import numpy as np
import os
import datetime
import requests
from dotenv import load_dotenv

# Configuración inicial de la página (DEBE SER LO PRIMERO)
st.set_page_config(
    page_title="Seguimiento de Pedidos",
    layout="wide",
    page_icon="📦",
    initial_sidebar_state="auto"
)

# Cargar variables de entorno
load_dotenv()
ONESIGNAL_APP_ID = os.getenv("ONESIGNAL_APP_ID")
ONESIGNAL_REST_API_KEY = os.getenv("ONESIGNAL_REST_API_KEY")
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")

# Estilos CSS personalizados
st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        color: white;
    }
    .stTextInput>div>div>input {
        color: #000000;
    }
    .st-b7 {
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------
# Funciones principales (optimizadas)
# ---------------------------------------------

@st.cache_data(ttl=60)  # Cache para mejor rendimiento
def cargar_datos():
    """Carga los datos con manejo robusto de errores"""
    try:
        if not os.path.exists("historico_estatus.xlsx"):
            return pd.DataFrame()
        
        df = pd.read_excel("historico_estatus.xlsx")
        
        # Conversión segura de tipos de datos
        df["Destino"] = df["Destino"].astype(str).str.strip()
        
        # Validar columnas esenciales
        columnas_requeridas = ["Destino", "Producto", "Estado de atención"]
        for col in columnas_requeridas:
            if col not in df.columns:
                st.error(f"Columna faltante: {col}")
                return pd.DataFrame()
                
        return df
    
    except Exception as e:
        st.error(f"Error al cargar datos: {str(e)}")
        return pd.DataFrame()

def mostrar_tarjetas(resultados):
    """Muestra los resultados en tarjetas visuales"""
    estado_colores = {
        "Entregado": "#1f8a70",
        "En proceso": "#f39c12",
        "Cancelado": "#c0392b",
        "Pendiente": "#3498db",
        "En ruta": "#8e44ad",
        "Sin asignar": "#95a5a6"
    }

    for _, row in resultados.iterrows():
        estado = row.get("Estado de atención", "Sin estado")
        color = estado_colores.get(estado, "#2c3e50")
        
        with st.container():
            st.markdown(f"""
                <div style='background-color:{color}; padding:15px; border-radius:10px; margin:10px 0;'>
                    <b>Producto:</b> {row.get('Producto', 'N/A')}<br>
                    <b>Destino:</b> {row.get('Destino', 'N/A')}<br>
                    <b>Estado:</b> {estado}<br>
                    <b>Capacidad:</b> {row.get('Capacidad programada (Litros)', 'N/A')}<br>
                    <b>Fecha estimada:</b> {row.get('Fecha y hora estimada', 'N/A')}
                </div>
            """, unsafe_allow_html=True)

def seccion_usuario():
    """Interfaz para usuarios normales"""
    st.title("📦 Seguimiento de Pedidos")
    
    destino = st.text_input("Ingrese número de destino", key="busqueda_destino").strip()
    
    if destino:
        df = cargar_datos()
        if not df.empty:
            resultados = df[df["Destino"].str.contains(destino, case=False, na=False)]
            
            if not resultados.empty:
                st.success(f"🔍 Resultados para: {destino}")
                mostrar_tarjetas(resultados)
            else:
                st.warning("No se encontraron pedidos para este destino")
        else:
            st.warning("Base de datos vacía. Contacte al administrador")

def seccion_admin():
    """Panel de administración"""
    st.title("🔧 Panel de Administración")
    
    # Barra de herramientas
    if st.button("🚪 Cerrar sesión"):
        st.session_state.admin_logged = False
        st.rerun()
    
    st.subheader("Cargar nuevos datos")
    archivo = st.file_uploader("Subir archivo Excel", type=["xlsx"])
    
    if archivo:
        try:
            nuevo_df = pd.read_excel(archivo)
            
            # Validación básica
            if "Destino" not in nuevo_df.columns:
                st.error("El archivo debe contener columna 'Destino'")
                return
                
            # Guardar datos
            nuevo_df.to_excel("historico_estatus.xlsx", index=False)
            st.success("✅ Datos actualizados correctamente!")
            st.balloons()
            
        except Exception as e:
            st.error(f"Error al procesar archivo: {str(e)}")

def login_panel():
    """Formulario de login"""
    st.title("🔐 Acceso Administrador")
    
    with st.form("login_form"):
        usuario = st.text_input("Usuario")
        contraseña = st.text_input("Contraseña", type="password")
        
        if st.form_submit_button("Ingresar"):
            if usuario == ADMIN_USER and contraseña == ADMIN_PASS:
                st.session_state.admin_logged = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas")

# ---------------------------------------------
# Estructura principal de la aplicación
# ---------------------------------------------

def main():
    # Inicialización de estado
    if "admin_logged" not in st.session_state:
        st.session_state.admin_logged = False
    
    # Menú de navegación
    st.sidebar.title("Navegación")
    opcion = st.sidebar.radio("Seleccione:", ["Usuario", "Administrador"])
    
    # Lógica de routing
    if opcion == "Usuario":
        seccion_usuario()
    else:
        if st.session_state.admin_logged:
            seccion_admin()
        else:
            login_panel()

if __name__ == "__main__":
    main()
