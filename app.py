import streamlit as st
import os
import pandas as pd
import requests
import datetime
import json
import hashlib
import altair as alt
import zoneinfo

# --- Zona Horaria ---
cdmx_tz = zoneinfo.ZoneInfo("America/Mexico_City")

# --- OneSignal Config desde secrets ---
APP_ID = st.secrets.get("ONESIGNAL_APP_ID")
REST_API_KEY = st.secrets.get("ONESIGNAL_REST_API_KEY")

# --- Credenciales admin desde secrets ---
ADMIN_USER = st.secrets.get("ADMIN_USER")
ADMIN_PASS = st.secrets.get("ADMIN_PASS")

# --- Rutas y archivos ---
# El archivo que se leerá para las búsquedas ahora es el histórico
HISTORIAL_EXCEL_PATH = "historial_general.xlsx"
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


# --- NUEVA FUNCIÓN: Enviar notificación a un destino específico ---
def enviar_notificacion_por_destino(destino, titulo, mensaje):
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
        # Filtra por el tag que crearemos con el ID del destino
        "filters": [
            {"field": "tag", "key": "destino_id", "relation": "=", "value": str(destino)}
        ],
        "headings": {"en": titulo},
        "contents": {"en": mensaje},
        "ios_sound": "default",
        "android_sound": "default"
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        st.success(f"✅ Notificación enviada al destino {destino}")
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
def calcular_hash_archivo(path):
    if not os.path.exists(path):
        return ""
    try:
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
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
    if os.path.exists(HISTORIAL_EXCEL_PATH):
        return pd.read_excel(HISTORIAL_EXCEL_PATH)
    return pd.DataFrame()

# --- Login ---
def login():
    st.title("🔐 Login Administrador")
    user = st.text_input("Usuario")
    pwd = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if user == ADMIN_USER and pwd == ADMIN_PASS:
            st.session_state.logged_in = True
            try:
                st.experimental_rerun()
            except AttributeError:
                st.rerun()
        else:
            st.error("❌ Usuario o contraseña incorrectos")

# --- Dashboard admin ---
def admin_dashboard():
    df = cargar_datos()
    if df.empty:
        st.info("Aún no hay archivo cargado.")
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

# --- NUEVA FUNCIÓN: Lógica para notificar solo si hay cambios de estado ---
def check_and_notify_on_change(old_df, new_df):
    
    # 1. Combina los dos dataframes para comparar
    merged_df = pd.merge(
        old_df, 
        new_df, 
        on='Destino', 
        how='inner', 
        suffixes=('_old', '_new')
    )

    # 2. Encuentra los destinos donde el estado ha cambiado
    cambios_df = merged_df[merged_df['Estado de atención_old'] != merged_df['Estado de atención_new']]
    
    if not cambios_df.empty:
        st.warning(f"🔔 Se detectaron {len(cambios_df)} cambios de estado. Enviando notificaciones...")
        for _, row in cambios_df.iterrows():
            destino = row['Destino']
            estado_anterior = row['Estado de atención_old']
            estado_nuevo = row['Estado de atención_new']
            
            titulo = f"Actualización en Destino: {destino}"
            mensaje = f"Estado cambió de '{estado_anterior}' a '{estado_nuevo}'"
            
            # 3. Envía la notificación solo a los usuarios suscritos a este destino
            enviar_notificacion_por_destino(destino, titulo, mensaje)
    else:
        st.info("✅ No se detectaron cambios en el estado de los destinos. No se enviaron notificaciones.")


# --- Panel Admin ---
def admin_panel():
    st.title("📤 Subida de archivo Excel")

    col1, col2 = st.columns([3, 1])

    with col1:
        uploaded_file = st.file_uploader("Selecciona archivo (.xlsx)", type=["xlsx"])
        if uploaded_file is not None:
            try:
                # Carga el archivo subido
                df_nuevo = pd.read_excel(uploaded_file)
                st.write("Vista previa del archivo cargado:")
                st.dataframe(df_nuevo.head())

                # Botón para cargar la base
                if st.button("Cargar y actualizar base histórica"):
                    # 1. Carga la base histórica existente (si existe)
                    if os.path.exists(HISTORIAL_EXCEL_PATH):
                        df_historico_old = pd.read_excel(HISTORIAL_EXCEL_PATH)
                    else:
                        df_historico_old = pd.DataFrame()

                    # 2. Revisa los cambios y envía notificaciones
                    if not df_historico_old.empty:
                        check_and_notify_on_change(df_historico_old, df_nuevo)
                    
                    # 3. Combina la información (opcional, podrías solo reemplazar si el archivo es la fuente de la verdad)
                    # Aquí la lógica asume que el nuevo archivo reemplaza el estado actual, por lo que lo guarda como el nuevo histórico.
                    df_nuevo.to_excel(HISTORIAL_EXCEL_PATH, index=False)
                    
                    # 4. Actualiza el historial de carga
                    ahora = datetime.datetime.now(tz=cdmx_tz).isoformat()
                    guardar_historial(ahora)
                    
                    st.success("✅ Base de datos histórica actualizada.")
                    
                    # Limpia la caché para que la consulta de usuario use los datos nuevos
                    st.cache_data.clear()

                    # Uso seguro de rerun
                    try:
                        st.experimental_rerun()
                    except AttributeError:
                        st.rerun()

            except Exception as e:
                st.error(f"Error al procesar archivo: {e}")

    with col2:
        with st.expander("📅 Historial de actualizaciones"):
            historial = cargar_historial()
            if historial:
                for i, fecha in enumerate(historial[::-1], 1):
                    try:
                        fecha_dt = datetime.datetime.fromisoformat(fecha)
                        st.write(f"{i}. {fecha_dt.strftime('%d/%m/%Y - %H:%M:%S Hrs.')} CDMX")
                    except ValueError:
                        st.write(f"{i}. (fecha inválida)")
            else:
                st.write("No hay actualizaciones aún.")

    admin_dashboard()

    if st.button("Cerrar sesión"):
        st.session_state.logged_in = False
        try:
            st.experimental_rerun()
        except AttributeError:
            st.rerun()

# --- Función para mostrar fichas visuales ---
def mostrar_fichas_visuales(df_resultado):
    colores = {
        "PROGRAMADO": (0, 123, 255),
        "FACTURADO": (40, 167, 69),
        "CANCELADO": (220, 53, 69),
        "CARGANDO": (255, 193, 7)
    }
    iconos = {
        "PROGRAMADO": "📅",
        "FACTURADO": "✅",
        "CANCELADO": "❌",
        "CARGANDO": "⏳"
    }

    for _, fila in df_resultado.iterrows():
        estado = str(fila.get("Estado de atención", "")).upper()
        if "CANCELADO" in estado:
            rgb = colores["CANCELADO"]
            icono = iconos["CANCELADO"]
        elif estado == "PROGRAMADO":
            rgb = colores["PROGRAMADO"]
            icono = iconos["PROGRAMADO"]
        elif estado == "FACTURADO":
            rgb = colores["FACTURADO"]
            icono = iconos["FACTURADO"]
        elif estado == "CARGANDO":
            rgb = colores["CARGANDO"]
            icono = iconos["CARGANDO"]
        else:
            rgb = (108, 117, 125)
            icono = "ℹ️"

        color_rgba = f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, 0.65)"
        
        # Obtiene el valor de la columna 'Destino'
        destino = fila.get('Destino', '')
        
        # Obtiene el valor de la columna 'Fecha'
        fecha_general = fila.get('Fecha', None)
        if pd.notnull(fecha_general) and isinstance(fecha_general, datetime.datetime):
            fecha_general = fecha_general.strftime('%d/%m/%Y')
        
        ficha_html = f"""
        <div style="
            background-color: {color_rgba};
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 10px;
            color: white;
            font-weight: 600;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            backdrop-filter: blur(6px);
            -webkit-backdrop-filter: blur(6px);
        ">
            <div style="font-size: 18px;">{icono} <b>{destino}</b></div>
            <div style="font-size: 14px; margin-top: 4px;">
        """
        
        if pd.notnull(fecha_general):
            ficha_html += f"<b>Fecha:</b> {fecha_general}<br>"
                
        ficha_html += f"""
                <b>Producto:</b> {fila.get('Producto', 'N/A')}<br>
                <b>Turno:</b> {fila.get('Turno', 'N/A')}<br>
                <b>Capacidad (L):</b> {fila.get('Capacidad programada (Litros)', 'N/A')}<br>
        """

        fecha_estimada = fila.get('Fecha y hora estimada', None)
        if pd.notnull(fecha_estimada):
            ficha_html += f"<b>Fecha Estimada:</b> {fecha_estimada}<br>"
        
        fecha_facturacion = fila.get('Fecha y hora de facturación', None)
        if pd.notnull(fecha_facturacion):
            ficha_html += f"<b>Fecha Facturación:</b> {fecha_facturacion}<br>"

        ficha_html += f"""
                <b>Estado:</b> {estado}
            </div>
        </div>
        """
        st.markdown(ficha_html, unsafe_allow_html=True)
        
        # --- NUEVO: Botón de suscripción por destino ---
        # El botón solo se muestra si el destino tiene un valor
        if destino and st.button(f"🔔 Suscribirme al Destino {destino}", key=f"sub_{destino}"):
            # Script para enviar el tag a OneSignal. La clave 'destino_id' debe coincidir con la del payload del admin.
            st.markdown(f"""
            <script>
            window.OneSignal = window.OneSignal || [];
            OneSignal.push(function() {{
                OneSignal.isPushNotificationsEnabled(function(isEnabled) {{
                    if (isEnabled) {{
                        OneSignal.sendTags({{
                            destino_id: "{destino}"
                        }}).then(function(tags) {{
                            console.log('Suscrito al destino:', tags);
                            alert('Te has suscrito a las notificaciones del Destino {destino}');
                        }});
                    }} else {{
                        alert('Por favor, activa las notificaciones para poder suscribirte.');
                        OneSignal.showSlidedownPrompt();
                    }}
                }});
            }});
            </script>
            """, unsafe_allow_html=True)


def user_panel():
    st.title("🔍 Consulta de Estatus")

    if not os.path.exists(HISTORIAL_EXCEL_PATH):
        st.info("Esperando que el admin suba un archivo.")
        return

    historial = cargar_historial()
    if historial:
        ultima_fecha_str = historial[-1]
        try:
            ultima_fecha = datetime.datetime.fromisoformat(ultima_fecha_str)
            ultima_fecha_cdmx = ultima_fecha.astimezone(cdmx_tz)
            st.info(f"📅 Última actualización: {ultima_fecha_cdmx.strftime('%d/%m/%Y - %H:%M Hrs.')} CDMX")
        except Exception:
            st.info("📅 Última actualización: (fecha inválida)")
    else:
        st.info("📅 Última actualización: (sin datos)")

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
        columnas = ['Destino', 'Fecha', 'Producto', 'Turno', 'Capacidad programada (Litros)',
                    'Fecha y hora estimada', 'Fecha y hora de facturación', 'Estado de atención']
        columnas_validas = [col for col in columnas if col in df.columns]

        df['Destino_num'] = df['Destino'].astype(str).str.split('-').str[0].str.strip()

        resultado = df[df['Destino_num'] == pedido.strip()]

        if not resultado.empty:
            resultado = resultado[columnas_validas].reset_index(drop=True)
            mostrar_fichas_visuales(resultado)
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
