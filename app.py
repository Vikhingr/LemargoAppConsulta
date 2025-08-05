import streamlit as st
import pandas as pd
import numpy as np
import os
from datetime import datetime
import requests
from streamlit_autorefresh import st_autorefresh
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Seguimiento de Pedidos", layout="wide", initial_sidebar_state="collapsed")

# Notificación con OneSignal
ONESIGNAL_APP_ID = os.getenv("ONESIGNAL_APP_ID")
ONESIGNAL_REST_API_KEY = os.getenv("ONESIGNAL_REST_API_KEY")
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")

# Constantes
HISTORICO_PATH = "historico_estatus.xlsx"
NUEVO_PATH = "nuevo_datos.xlsx"

# Estilo dark + moderno
def dark_mode_style():
    st.markdown("""
        <style>
            body { color: #f0f2f6; background-color: #0e1117; }
            .stApp { background-color: #0e1117; }
            .card { 
                background-color: #1e222d; 
                border-radius: 1rem; 
                padding: 1.2rem; 
                margin-bottom: 1rem; 
                box-shadow: 0 4px 10px rgba(0,0,0,0.3); 
                color: #f0f2f6;
            }
            .card h4 { margin: 0 0 0.5rem 0; }
        </style>
    """, unsafe_allow_html=True)

dark_mode_style()

# Cargar archivos
def cargar_datos(path):
    if os.path.exists(path):
        return pd.read_excel(path)
    return pd.DataFrame()

def guardar_datos(df, path):
    df.to_excel(path, index=False)

def limpiar_columnas(df):
    df.columns = df.columns.str.strip()
    return df

# Filtrado exacto por número de destino
def filtrar_por_destino(df, destino):
    return df[df['Destino'].astype(str) == str(destino)]

# Eliminar duplicados dejando solo el más reciente
def eliminar_duplicados(df):
    df = df.sort_values("Fecha", ascending=False)
    return df.drop_duplicates(subset=["Destino", "Fecha"], keep="first")

# Mostrar los resultados en tarjetas visuales
def mostrar_resultados(df_filtrado):
    if df_filtrado.empty:
        st.info("No se encontraron pedidos para ese destino.")
        return

    df_filtrado = eliminar_duplicados(df_filtrado)

    for _, row in df_filtrado.iterrows():
        with st.container():
            st.markdown(f"""
            <div class="card">
                <h4>Producto: {row['Producto']}</h4>
                <p><strong>Turno:</strong> {row['Turno']}</p>
                <p><strong>Tonel:</strong> {row['Tonel'] if 'Tonel' in row else 'N/D'}</p>
                <p><strong>Capacidad programada:</strong> {row['Capacidad programada (Litros)']} L</p>
                <p><strong>Fecha estimada:</strong> {row['Fecha y hora estimada']}</p>
                <p><strong>Fecha de facturación:</strong> {row['Fecha y hora de facturación']}</p>
                <p><strong>Estado de atención:</strong> {row['Estado de atención']}</p>
            </div>
            """, unsafe_allow_html=True)

# Subscripción OneSignal
def mostrar_boton_suscripcion(destino):
    st.markdown("---")
    st.subheader("🔔 Notificaciones")
    st.markdown("Recibirás notificaciones automáticas cuando cambie el estatus de este destino.")

    st.markdown(f"""
    <script>
      window.OneSignal = window.OneSignal || [];
      OneSignal.push(function() {{
        OneSignal.init({{
          appId: "{ONESIGNAL_APP_ID}",
          notifyButton: {{
            enable: true,
          }},
          promptOptions: {{
            slidedown: {{
              prompts: [{{
                type: "category",
                autoPrompt: true,
                categories: ["destino_{destino}"]
              }}]
            }}
          }}
        }});
      }});
    </script>
    """, unsafe_allow_html=True)

# Interfaz de usuario
def seccion_usuario():
    st.title("🔍 Consulta tu Pedido")
    st.markdown("Ingresa el número de destino para consultar su estatus actual.")

    destino_input = st.text_input("Número de destino", max_chars=10)

    if destino_input:
        df = cargar_datos(HISTORICO_PATH)
        df = limpiar_columnas(df)

        df_filtrado = filtrar_por_destino(df, destino_input)

        mostrar_resultados(df_filtrado)
        mostrar_boton_suscripcion(destino_input)

# Sección administrador (login simple + carga de archivo nuevo)
def seccion_admin():
    st.title("🛠️ Panel de Administrador")

    uploaded_file = st.file_uploader("Cargar nuevo archivo de datos (.xlsx)", type=["xlsx"])
    if uploaded_file:
        df_nuevo = pd.read_excel(uploaded_file)
        df_nuevo = limpiar_columnas(df_nuevo)

        # Guardar nuevo archivo
        guardar_datos(df_nuevo, NUEVO_PATH)
        st.success("✅ Archivo cargado correctamente. Puedes actualizar la base.")

    if st.button("🔄 Actualizar Base"):
        df_hist = cargar_datos(HISTORICO_PATH)
        df_nuevo = cargar_datos(NUEVO_PATH)

        if not df_nuevo.empty:
            df_comb = pd.concat([df_hist, df_nuevo])
            df_comb.drop_duplicates(subset=["Destino", "Fecha"], keep="last", inplace=True)
            guardar_datos(df_comb, HISTORICO_PATH)
            st.success("✅ Base histórica actualizada.")
        else:
            st.warning("⚠️ No hay nuevo archivo para actualizar.")

# Login de administrador
def login_panel():
    with st.sidebar:
        st.title("🔐 Acceso Admin")
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        login = st.button("Iniciar sesión")

    if login and username == ADMIN_USER and password == ADMIN_PASS:
        st.session_state["admin_logged_in"] = True
        st.experimental_rerun()
    elif login:
        st.error("Credenciales incorrectas")

def main():
    if "admin_logged_in" not in st.session_state:
        st.session_state["admin_logged_in"] = False

    menu = st.sidebar.radio("Navegación", ["Consulta", "Administrador"])

    if menu == "Consulta":
        seccion_usuario()
    elif menu == "Administrador":
        if st.session_state["admin_logged_in"]:
            seccion_admin()
        else:
            login_panel()

if __name__ == "__main__":
    main()
