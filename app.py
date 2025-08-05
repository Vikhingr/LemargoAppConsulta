import streamlit as st
import pandas as pd
import os
import requests

# Configuración inicial (DEBE SER LO PRIMERO)
st.set_page_config(
    page_title="Seguimiento de Pedidos",
    layout="wide",
    page_icon="📦",
    initial_sidebar_state="auto"
)

# ---------------------------------------------
# 1. Configuración de Secrets (Streamlit Cloud)
# ---------------------------------------------

# Verificación de secrets (para debug)
st.sidebar.write("🔍 Secrets cargados:", list(st.secrets.keys()))

try:
    # Carga de variables desde secrets
    ONESIGNAL_APP_ID = st.secrets["ONESIGNAL_APP_ID"]
    ONESIGNAL_REST_API_KEY = st.secrets["ONESIGNAL_REST_API_KEY"]
    ADMIN_USER = st.secrets["ADMIN_USER"]
    ADMIN_PASS = st.secrets["ADMIN_PASS"]
    
    # Verificación básica
    if not all([ONESIGNAL_APP_ID, ONESIGNAL_REST_API_KEY, ADMIN_USER, ADMIN_PASS]):
        st.error("❌ Faltan variables esenciales en los secrets")
        st.stop()
        
except Exception as e:
    st.error(f"❌ Error crítico cargando configuración: {str(e)}")
    st.stop()

# ---------------------------------------------
# 2. Estilos CSS
# ---------------------------------------------
st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        color: white;
    }
    .stTextInput>div>div>input {
        color: #000000;
        background-color: #ffffff;
    }
    .st-b7 {
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------
# 3. Funciones Principales (Optimizadas)
# ---------------------------------------------

@st.cache_data(ttl=60, show_spinner="Cargando datos...")
def cargar_datos():
    """Carga los datos con manejo robusto de errores"""
    try:
        if not os.path.exists("historico_estatus.xlsx"):
            return pd.DataFrame()
        
        df = pd.read_excel("historico_estatus.xlsx")
        
        # Conversión y limpieza
        df["Destino"] = df["Destino"].astype(str).str.strip()
        
        # Validación de columnas
        required_columns = ["Destino", "Producto", "Estado de atención", 
                          "Capacidad programada (Litros)", "Fecha y hora estimada"]
        missing = [col for col in required_columns if col not in df.columns]
        
        if missing:
            st.error(f"Columnas faltantes: {', '.join(missing)}")
            return pd.DataFrame()
            
        return df
    
    except Exception as e:
        st.error(f"📂 Error al cargar datos: {str(e)}")
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
                <div style='background-color:{color}; 
                            padding:15px; 
                            border-radius:10px; 
                            margin:10px 0;
                            color:white;'>
                    <b>Producto:</b> {row.get('Producto', 'N/A')}<br>
                    <b>Destino:</b> {row.get('Destino', 'N/A')}<br>
                    <b>Estado:</b> {estado}<br>
                    <b>Capacidad:</b> {row.get('Capacidad programada (Litros)', 'N/A')}<br>
                    <b>Fecha estimada:</b> {row.get('Fecha y hora estimada', 'N/A')}
                </div>
            """, unsafe_allow_html=True)

# ---------------------------------------------
# 4. Secciones de la Aplicación
# ---------------------------------------------

def seccion_usuario():
    """Interfaz para usuarios normales"""
    st.title("📦 Seguimiento de Pedidos")
    
    with st.form("busqueda_form"):
        destino = st.text_input("Ingrese número de destino", key="busqueda_destino").strip()
        submitted = st.form_submit_button("Buscar")
        
        if submitted and destino:
            with st.spinner("Buscando pedidos..."):
                df = cargar_datos()
                
                if not df.empty:
                    resultados = df[df["Destino"].str.contains(destino, case=False, na=False)]
                    
                    if not resultados.empty:
                        st.success(f"🔍 {len(resultados)} resultados para: {destino}")
                        mostrar_tarjetas(resultados)
                    else:
                        st.warning("No se encontraron pedidos para este destino")
                else:
                    st.warning("Base de datos vacía. Contacte al administrador")

def seccion_admin():
    """Panel de administración mejorado"""
    st.title("🔧 Panel de Administración")
    
    # Barra de herramientas
    if st.button("🚪 Cerrar sesión", key="logout_btn"):
        st.session_state.admin_logged = False
        st.rerun()
    
    st.subheader("Gestión de Datos")
    tab1, tab2 = st.tabs(["Cargar Datos", "Estadísticas"])
    
    with tab1:
        archivo = st.file_uploader("Subir archivo Excel", type=["xlsx"], key="file_uploader")
        
        if archivo:
            try:
                nuevo_df = pd.read_excel(archivo)
                
                # Validación mejorada
                required = ["Destino", "Producto", "Estado de atención"]
                missing = [col for col in required if col not in nuevo_df.columns]
                
                if missing:
                    st.error(f"Faltan columnas: {', '.join(missing)}")
                else:
                    # Procesamiento seguro
                    nuevo_df["Destino"] = nuevo_df["Destino"].astype(str).str.strip()
                    nuevo_df.to_excel("historico_estatus.xlsx", index=False)
                    
                    st.success("✅ Datos actualizados correctamente!")
                    st.balloons()
                    
                    # Vista previa
                    with st.expander("Ver datos cargados"):
                        st.dataframe(nuevo_df.head())
                        
            except Exception as e:
                st.error(f"❌ Error al procesar archivo: {str(e)}")
    
    with tab2:
        if os.path.exists("historico_estatus.xlsx"):
            df = cargar_datos()
            if not df.empty:
                st.metric("Total Pedidos", len(df))
                st.bar_chart(df["Estado de atención"].value_counts())
            else:
                st.warning("No hay datos disponibles")

def login_panel():
    """Formulario de login mejorado"""
    st.title("🔐 Acceso Administrador")
    
    with st.form("login_form", clear_on_submit=True):
        usuario = st.text_input("Usuario", key="user_input")
        contraseña = st.text_input("Contraseña", type="password", key="pass_input")
        
        if st.form_submit_button("Ingresar", type="primary"):
            if usuario == ADMIN_USER and contraseña == ADMIN_PASS:
                st.session_state.admin_logged = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas")

# ---------------------------------------------
# 5. Estructura Principal
# ---------------------------------------------

def main():
    # Inicialización de estado
    if "admin_logged" not in st.session_state:
        st.session_state.admin_logged = False
    
    # Menú de navegación
    st.sidebar.title("Navegación")
    opcion = st.sidebar.radio(
        "Seleccione:", 
        ["Usuario", "Administrador"],
        index=0
    )
    
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
