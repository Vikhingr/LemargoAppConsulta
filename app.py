import streamlit as st
import os
import pandas as pd
import requests
import datetime
import json
import hashlib
import altair as alt

# --- OneSignal Config desde secrets ---
APP_ID = st.secrets.get("ONESIGNAL_APP_ID")
REST_API_KEY = st.secrets.get("ONESIGNAL_REST_API_KEY")

# --- Credenciales admin desde secrets ---
ADMIN_USER = st.secrets.get("ADMIN_USER")
ADMIN_PASS = st.secrets.get("ADMIN_PASS")

# --- Rutas y archivos ---
EXCEL_PATH = "archivo_cargado.xlsx"
HISTORIAL_PATH = "historial_actualizaciones.json"
HASH_PATH = "hash_actual.txt"

# --- PWA Setup (manifest e iconos) ---
def pwa_setup():
    st.markdown("""
        <link rel="manifest" href="manifest.json">
        <meta name="theme-color" content="#0f1116">
        <meta name="mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="black">
        <link rel="apple-touch-icon" href="Lemargo-192x192.png">
        <link rel="icon" type="image/png" sizes="192x192" href="Lemargo-192x192.png">
    """, unsafe_allow_html=True)

# --- OneSignal Web Push Setup con prompt automático ---
def onesignal_web_push_setup():
    if not APP_ID:
        st.error("❌ APP_ID de OneSignal no configurado en secrets.")
        return

    st.markdown(f"""
    <script>
    (function() {{
        function loadOneSignalSDK(callback) {{
            var script = document.createElement('script');
            script.src = "https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.page.js";
            script.async = true;
            script.onload = callback;
            document.head.appendChild(script);
        }}

        function initOneSignal() {{
            window.OneSignal = window.OneSignal || [];
            OneSignal.push(function() {{
                OneSignal.init({{
                    appId: "{APP_ID}",
                    notifyButton: {{
                        enable: true,
                    }},
                    allowLocalhostAsSecureOrigin: true,
                    serviceWorkerPath: "/OneSignalSDKWorker.js",
                    serviceWorkerUpdaterPath: "/OneSignalSDKUpdaterWorker.js"
                }});
                OneSignal.showSlidedownPrompt();
            }});
        }}

        if (typeof OneSignal === "undefined") {{
            loadOneSignalSDK(initOneSignal);
        }} else {{
            initOneSignal();
        }}
    }})();
    </script>
    """, unsafe_allow_html=True)

# --- Banner instalación PWA (opcional, ya que el prompt es automático) ---
def pwa_install_prompt():
    st.markdown("""
    <script>
      let deferredPrompt;
      window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;
        // Prompt automático:
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then((choiceResult) => {
          if(choiceResult.outcome === 'accepted'){
            console.log('Usuario aceptó instalar');
          } else {
            console.log('Usuario rechazó instalar');
          }
          deferredPrompt = null;
        });
      });
    </script>
    """, unsafe_allow_html=True)

# --- Enviar notificación ---
def enviar_notificacion(titulo, mensaje):
    if not REST_API_KEY or not APP_ID:
        st.error("❌ Claves OneSignal no configuradas correctamente.")
        return

    url = "https://onesignal.com/api/v1/notifications"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Basic {REST_API_KEY}"
    }
    payload = {
        "app_id": APP_ID,
        "included_segments": ["All"],
        "headings": {"en": titulo},
        "contents": {"en": mensaje},
        "ios_sound": "default",
        "android_sound": "default"
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        st.success("✅ Notificación enviada")
    except requests.RequestException as e:
        st.error(f"❌ Error al enviar notificación: {e}")

# --- Historial ---
def cargar_historial():
    if os.path.exists(HISTORIAL_PATH):
        try:
            with open(HISTORIAL_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def guardar_historial(fecha_hora):
    historial = cargar_historial()
    historial.append(fecha_hora)
    try:
        with open(HISTORIAL_PATH, "w") as f:
            json.dump(historial, f)
    except Exception as e:
        st.error(f"Error guardando historial: {e}")

# --- Hash archivo con SHA256 ---
def calcular_hash_archivo():
    if not os.path.exists(EXCEL_PATH):
        return ""
    try:
        hasher = hashlib.sha256()
        with open(EXCEL_PATH, "rb") as f:
            buf = f.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()
    except Exception as e:
        st.error(f"Error calculando hash archivo: {e}")
        return ""

def guardar_hash_actual(hash_valor):
    try:
        with open(HASH_PATH, "w") as f:
            f.write(hash_valor)
    except Exception as e:
        st.error(f"Error guardando hash: {e}")

def cargar_hash_guardado():
    if os.path.exists(HASH_PATH):
        try:
            with open(HASH_PATH, "r") as f:
                return f.read()
        except Exception:
            return ""
    return ""

# --- Datos con cache ---
@st.cache_data(show_spinner=False)
def cargar_datos():
    return pd.read_excel(EXCEL_PATH)

# --- Login ---
def login():
    st.title("🔐 Login Administrador")
    user = st.text_input("Usuario")
    pwd = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if user == ADMIN_USER and pwd == ADMIN_PASS:
            st.session_state.logged_in = True
            # Uso seguro de rerun
            try:
                st.experimental_rerun()
            except AttributeError:
                st.rerun()
        else:
            st.error("❌ Usuario o contraseña incorrectos")

# --- Dashboard admin ---
def admin_dashboard():
    if not os.path.exists(EXCEL_PATH):
        st.info("Aún no hay archivo cargado.")
        return

    try:
        df = cargar_datos()
    except Exception as e:
        st.error(f"Error leyendo archivo: {e}")
        return

    st.subheader("📊 Visualización de datos")

    if 'Estado de atención' in df.columns:
        conteo_estado = df['Estado de atención'].value_counts().reset_index()
        conteo_estado.columns = ['Estado', 'Cantidad']
        chart_estado = alt.Chart(conteo_estado).mark_bar().encode(
            x=alt.X('Estado', sort='-y'),
            y='Cantidad',
            color='Estado'
        ).properties(width=600)
        st.altair_chart(chart_estado)

    if 'Destino' in df.columns:
        conteo_destino = df['Destino'].value_counts().reset_index()
        conteo_destino.columns = ['Destino', 'Cantidad']
        chart_destino = alt.Chart(conteo_destino).mark_bar().encode(
            x=alt.X('Destino', sort='-y'),
            y='Cantidad',
            color='Destino'
        ).properties(width=600)
        st.altair_chart(chart_destino)

# --- Panel Admin ---
def admin_panel():
    st.title("📤 Subida de archivo Excel")

    col1, col2 = st.columns([3, 1])

    with col1:
        uploaded_file = st.file_uploader("Selecciona archivo (.xlsx)", type=["xlsx"])
        if uploaded_file is not None:
            try:
                with open(EXCEL_PATH, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                nuevo_hash = calcular_hash_archivo()
                hash_guardado = cargar_hash_guardado()

                if nuevo_hash != hash_guardado:
                    guardar_hash_actual(nuevo_hash)

                    ahora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    guardar_historial(ahora)

                    enviar_notificacion("Actualización", "La base de datos ha sido actualizada.")
                    st.success("Archivo cargado y notificación enviada.")
                else:
                    st.info("El archivo cargado es igual al anterior. No se envió notificación.")

                # Uso seguro de rerun
                try:
                    st.experimental_rerun()
                except AttributeError:
                    st.rerun()
            except Exception as e:
                st.error(f"Error al guardar archivo: {e}")

    with col2:
        with st.expander("📅 Historial de actualizaciones"):
            historial = cargar_historial()
            if historial:
                for i, fecha in enumerate(historial[::-1], 1):
                    st.write(f"{i}. {fecha}")
            else:
                st.write("No hay actualizaciones aún.")

    admin_dashboard()

    if st.button("Cerrar sesión"):
        st.session_state.logged_in = False
        # Uso seguro de rerun
        try:
            st.experimental_rerun()
        except AttributeError:
            st.rerun()

def user_panel():
    st.title("🔍 Consulta de Estatus")

    if not os.path.exists(EXCEL_PATH):
        st.info("Esperando que el admin suba un archivo.")
        return

    # Mostrar última actualización
    timestamp = os.path.getmtime(EXCEL_PATH)
    ultima_mod = datetime.datetime.fromtimestamp(timestamp)
    st.info(f"📅 Última actualización: {ultima_mod.strftime('%d/%m/%Y - %H:%M Hrs.')}")

    try:
        df = cargar_datos()
    except Exception as e:
        st.error(f"Error al leer archivo: {e}")
        return

    if 'Destino' not in df.columns:
        st.error("❌ Falta la columna 'Destino'")
        return

    pedido = st.text_input("Ingresa tu número de destino")
    if pedido:
        columnas = ['Destino', 'Producto', 'Turno', 'Capacidad programada (Litros)',
                    'Fecha y hora estimada', 'Fecha y hora de facturación', 'Estado de atención']
        columnas_validas = [col for col in columnas if col in df.columns]

        # Extraer número del destino para búsqueda exacta
        df['Destino_num'] = df['Destino'].astype(str).str.split('-').str[0].str.strip()

        resultado = df[df['Destino_num'] == pedido.strip()]

        if not resultado.empty:
            resultado = resultado[columnas_validas].reset_index(drop=True)
            st.dataframe(resultado.style.set_properties(**{
                'text-align': 'center'
            }))
        else:
            st.warning("No se encontraron resultados.")


# --- App principal ---
def main():
    pwa_setup()
    onesignal_web_push_setup()
    pwa_install_prompt()

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    menu = st.sidebar.radio("📋 Menú principal", ["Consultar estatus", "Admin Login"])

    if menu == "Consultar estatus":
        user_panel()
    elif menu == "Admin Login":
        if not st.session_state.logged_in:
            login()
        else:
            st.success("🛠️ Sesión iniciada como administrador")
            admin_panel()

if __name__ == "__main__":
    main()
