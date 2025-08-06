import streamlit as st
import os
import pandas as pd
import requests
import datetime
import json
import altair as alt
import zoneinfo

# --- Configuración de Zona Horaria ---
# Define la zona horaria de la Ciudad de México para manejar fechas y horas.
cdmx_tz = zoneinfo.ZoneInfo("America/Mexico_City")

# --- Importaciones y Configuración de Firebase Admin SDK ---
# Importa los módulos necesarios de Firebase Admin SDK para interactuar con Firebase.
import firebase_admin
from firebase_admin import credentials, messaging

# --- Carga Segura de Credenciales de Firebase ---
# Carga las claves de Firebase (cuenta de servicio, clave VAPID y configuración del frontend)
# directamente desde los secretos configurados en Streamlit Cloud.
try:
    FIREBASE_SERVICE_ACCOUNT_JSON = json.loads(st.secrets.get("FIREBASE_SERVICE_ACCOUNT"))
    FIREBASE_VAPID_KEY = st.secrets.get("FIREBASE_VAPID_KEY")
    FIREBASE_CONFIG = st.secrets.get("FIREBASE_CONFIG")
    
    # Inicializa el SDK de Firebase Admin si aún no está inicializado.
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_JSON)
        firebase_admin.initialize_app(cred)
    st.info("✅ Firebase Admin SDK inicializado correctamente.")
except Exception as e:
    st.error(f"❌ Error al inicializar Firebase Admin SDK. Asegúrate de que las claves estén en los Secrets de Streamlit Cloud. Error: {e}")
    st.stop() # Detiene la ejecución de la aplicación si hay un error crítico.

# --- Credenciales de Administrador ---
# Carga el usuario y la contraseña del administrador desde los secretos de Streamlit Cloud.
ADMIN_USER = st.secrets.get("ADMIN_USER")
ADMIN_PASS = st.secrets.get("ADMIN_PASS")

# --- Rutas de Archivos de Datos ---
# Define las rutas para la base de datos principal y el historial de actualizaciones.
DB_PATH = "golden_record.json"
HISTORIAL_PATH = "historial_actualizaciones.json"

# --- Configuración de PWA (Progressive Web App) ---
# Inserta etiquetas HTML para configurar la aplicación como una PWA, incluyendo el manifiesto y los iconos.
def pwa_setup():
    st.markdown("""
        <link rel="manifest" href="public/manifest.json">
        <meta name="theme-color" content="#0f1116">
        <meta name="mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="black">
        <link rel="apple-touch-icon" href="public/icons/icon-192.png">
        <link rel="icon" type="image/png" sizes="192x192" href="public/icons/icon-192.png">
    """, unsafe_allow_html=True)

# --- Configuración de Firebase Cloud Messaging (FCM) en el Frontend ---
# Inserta el código JavaScript necesario para inicializar Firebase en el navegador,
# solicitar permisos de notificación y obtener el token de registro de FCM.
def fcm_pwa_setup():
    firebase_config_js = st.secrets.get("FIREBASE_CONFIG")
    vapid_key_js = st.secrets.get("FIREBASE_VAPID_KEY")

    st.markdown(f"""
    <script>
    // Importa los módulos de Firebase de forma asíncrona.
    import('https://www.gstatic.com/firebasejs/8.10.0/firebase-app.js')
        .then((module) => {{
            const firebase = module.default;
            // Inicializa la aplicación Firebase con la configuración proporcionada.
            firebase.initializeApp(JSON.parse('{firebase_config_js}'));

            // Carga el módulo de mensajería de Firebase.
            return import('https://www.gstatic.com/firebasejs/8.10.0/firebase-messaging.js');
        }})
        .then((module) => {{
            const messaging = module.default();

            // Función para obtener el token de registro de FCM.
            function getFcmToken() {{
                messaging.getToken({{ vapidKey: '{vapid_key_js}' }}).then((currentToken) => {{
                    if (currentToken) {{
                        // Muestra el token en la consola y en una alerta para que el usuario lo copie.
                        console.log('FCM Registration Token:', currentToken);
                        alert('Tu token de suscripción está en la consola del navegador (F12). Cópialo y pégalo en el campo de abajo.');
                    }} else {{
                        console.log('No se pudo obtener el token. Solicita permiso para generar uno.');
                        alert('Para recibir notificaciones, por favor, activa las notificaciones en tu navegador.');
                    }}
                }}).catch((err) => {{
                    console.log('Ocurrió un error al obtener el token: ', err);
                    alert('Error al obtener el token de notificación.');
                }});
            }}
            
            // Llama a getFcmToken cuando la ventana se carga para solicitar el token.
            window.onload = getFcmToken;

            // Escucha las notificaciones cuando la aplicación está en primer plano.
            messaging.onMessage(function(payload) {{
                console.log('Mensaje recibido en primer plano: ', payload);
                alert(payload.notification.title + ": " + payload.notification.body);
            }});
        }})
        .catch((err) => {{
            console.error("Error al cargar los scripts de Firebase", err);
        }});
    </script>
    """, unsafe_allow_html=True)

# --- Función para Enviar Notificaciones Push con FCM ---
# Envía una notificación push a un token de registro de FCM específico utilizando Firebase Admin SDK.
def enviar_notificacion_por_token(token, titulo, mensaje):
    if not token:
        st.error("❌ No hay un token de FCM válido para enviar la notificación.")
        return

    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=titulo,
                body=mensaje,
            ),
            token=token,
        )
        response = messaging.send(message)
        st.success(f"✅ Notificación enviada con éxito. ID de respuesta: {response}")
    except Exception as e:
        st.error(f"❌ Error al enviar notificación: {e}")

# --- Carga de Historial de Actualizaciones ---
# Carga el historial de las fechas de actualización de la base de datos desde un archivo JSON.
def cargar_historial():
    if os.path.exists(HISTORIAL_PATH):
        try:
            with open(HISTORIAL_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

# --- Guardado de Historial de Actualizaciones ---
# Guarda una nueva fecha de actualización en el historial.
def guardar_historial(fecha_hora):
    historial = cargar_historial()
    historial.append(fecha_hora)
    try:
        with open(HISTORIAL_PATH, "w") as f:
            json.dump(historial, f)
    except Exception as e:
        st.error(f"Error guardando historial: {e}")

# --- Carga de Datos (con caché) ---
# Carga la base de datos principal desde un archivo JSON, utilizando caché para optimizar el rendimiento.
@st.cache_data(show_spinner=False)
def cargar_datos():
    if os.path.exists(DB_PATH):
        try:
            df = pd.read_json(DB_PATH)
            return df
        except Exception as e:
            st.error(f"Error al cargar la base de datos histórica: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# --- Guardado de Datos ---
# Guarda el DataFrame actual en el archivo JSON de la base de datos.
def guardar_datos(df):
    try:
        if 'Fecha' in df.columns:
            df['Fecha'] = pd.to_datetime(df['Fecha']).dt.strftime('%Y-%m-%d')
        df.to_json(DB_PATH, orient='records', date_format='iso')
    except Exception as e:
        st.error(f"Error al guardar la base de datos: {e}")

# --- Lógica de Inicio de Sesión de Administrador ---
# Muestra un formulario de inicio de sesión para el administrador.
def login():
    st.title("🔐 Login Administrador")
    user = st.text_input("Usuario")
    pwd = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if user == ADMIN_USER and pwd == ADMIN_PASS:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("❌ Usuario o contraseña incorrectos")

# --- Dashboard de Administración ---
# Muestra visualizaciones y análisis de los datos cargados, con filtros por producto, estado y fecha.
def admin_dashboard():
    df = cargar_datos()
    if df.empty:
        st.info("Aún no hay base de datos cargada.")
        return

    st.subheader("📊 Visualización y análisis de datos")

    columnas_disponibles = df.columns.tolist()

    if 'Fecha' in columnas_disponibles:
        df['Fecha'] = pd.to_datetime(df['Fecha']).dt.date
    else:
        st.warning("La columna 'Fecha' no se encontró en la base de datos. No se podrá filtrar por fecha.")
        return

    st.markdown("#### Filtros")
    col1, col2, col3 = st.columns(3)

    with col1:
        if 'Producto' in columnas_disponibles:
            productos = df['Producto'].unique().tolist()
            productos_seleccionados = st.multiselect("Filtrar por Producto", options=productos, default=productos)
        else:
            productos_seleccionados = []
            st.warning("Columna 'Producto' no encontrada.")

    with col2:
        if 'Estado de atención' in columnas_disponibles:
            estados = df['Estado de atención'].unique().tolist()
            estados_seleccionados = st.multiselect("Filtrar por Estado", options=estados, default=estados)
        else:
            estados_seleccionados = []
            st.warning("Columna 'Estado de atención' no encontrada.")

    with col3:
        fechas = sorted(df['Fecha'].unique().tolist(), reverse=True)
        if fechas:
            fecha_seleccionada = st.selectbox("Selecciona una fecha", options=fechas, format_func=lambda x: x.strftime('%d/%m/%Y'))
        else:
            st.warning("No hay fechas disponibles para filtrar.")
            return

    df_filtrado = df[df['Fecha'] == fecha_seleccionada]
    if productos_seleccionados:
        df_filtrado = df_filtrado[df_filtrado['Producto'].isin(productos_seleccionados)]
    if estados_seleccionados:
        df_filtrado = df_filtrado[df_filtrado['Estado de atención'].isin(estados_seleccionados)]

    if df_filtrado.empty:
        st.warning("No hay datos que coincidan con los filtros seleccionados.")
        return

    st.markdown("---")
    st.subheader(f"Análisis del día: {fecha_seleccionada.strftime('%d/%m/%Y')}")

    # Gráfica 1: ESTADO DE ATENCIÓN (del día filtrado)
    if 'Estado de atención' in df_filtrado.columns:
        st.markdown("#### Conteo por Estado de atención")
        conteo_estado = df_filtrado['Estado de atención'].value_counts().reset_index()
        conteo_estado.columns = ['Estado', 'Cantidad']

        chart_estado = alt.Chart(conteo_estado).mark_bar(
            cornerRadiusTopLeft=3,
            cornerRadiusTopRight=3,
            color='#4e79a7'
        ).encode(
            x=alt.X('Estado', sort='-y', title='Estado de atención'),
            y=alt.Y('Cantidad', title='Número de registros'),
            tooltip=['Estado', 'Cantidad'],
        ).properties(title='Distribución por Estado')
        st.altair_chart(chart_estado, use_container_width=True)

    # Gráfica 2: CONTEO POR DESTINO (del día filtrado)
    if 'Destino' in df_filtrado.columns:
        st.markdown("#### Conteo por Destino")
        conteo_destino = df_filtrado['Destino'].value_counts().reset_index()
        conteo_destino.columns = ['Destino', 'Cantidad']

        chart_destino = alt.Chart(conteo_destino).mark_bar(
            cornerRadiusTopLeft=3,
            cornerRadiusTopRight=3,
            color='#59a14f'
        ).encode(
            x=alt.X('Cantidad', title='Número de registros'),
            y=alt.Y('Destino', sort='-x', title='Destino'),
            tooltip=['Destino', 'Cantidad'],
        ).properties(title='Conteo de Registros por Destino')
        st.altair_chart(chart_destino, use_container_width=True)

    st.markdown("---")
    st.markdown("#### 📝 Datos filtrados del día")
    st.dataframe(df_filtrado)

    # --- Análisis Histórico Acumulado (TOP 10) ---
    st.markdown("---")
    st.subheader("🏆 Análisis histórico - Top 10 Destinos")
    st.info("Estas gráficas se basan en **todos los datos del archivo histórico**.")

    if 'Destino' in df.columns and 'Estado de atención' in df.columns:
        # 1. TOP 10 FACTURADOS
        df_historico_facturados = df[df['Estado de atención'].str.contains('FACTURADO', case=False, na=False)]
        if not df_historico_facturados.empty:
            top_10_facturados = df_historico_facturados['Destino'].value_counts().nlargest(10).reset_index()
            top_10_facturados.columns = ['Destino', 'Cantidad']
            st.markdown("#### Top 10 Destinos más facturados (Histórico)")
            st.dataframe(top_10_facturados, use_container_width=True)

            chart_top_facturados = alt.Chart(top_10_facturados).mark_bar(
                color='#4caf50' # Verde
            ).encode(
                x=alt.X('Cantidad', title='Número de Facturaciones'),
                y=alt.Y('Destino', sort='-x', title='Destino'),
                tooltip=['Destino', 'Cantidad']
            ).properties(
                title='Top 10 Facturados Acumulado'
            )
            st.altair_chart(chart_top_facturados, use_container_width=True)

        # 2. TOP 10 CANCELADOS
        df_historico_cancelados = df[df['Estado de atención'].str.contains('CANCELADO', case=False, na=False)]
        if not df_historico_cancelados.empty:
            top_10_cancelados = df_historico_cancelados['Destino'].value_counts().nlargest(10).reset_index()
            top_10_cancelados.columns = ['Destino', 'Cantidad']
            st.markdown("#### Top 10 Destinos más cancelados (Histórico)")
            st.dataframe(top_10_cancelados, use_container_width=True)

            chart_top_cancelados = alt.Chart(top_10_cancelados).mark_bar(
                color='#f44336' # Rojo
            ).encode(
                x=alt.X('Cantidad', title='Número de Cancelaciones'),
                y=alt.Y('Destino', sort='-x', title='Destino'),
                tooltip=['Destino', 'Cantidad']
            ).properties(
                title='Top 10 Cancelados Acumulado'
            )
            st.altair_chart(chart_top_cancelados, use_container_width=True)

        # 3. TOP 10 CON DEMORA (no facturados y no cancelados)
        df_historico_demorados = df[~df['Estado de atención'].str.contains('FACTURADO|CANCELADO', case=False, na=False)]
        if not df_historico_demorados.empty:
            top_10_demorados = df_historico_demorados['Destino'].value_counts().nlargest(10).reset_index()
            top_10_demorados.columns = ['Destino', 'Cantidad']
            st.markdown("#### Top 10 Destinos con más demora (Histórico)")
            st.dataframe(top_10_demorados, use_container_width=True)

            chart_top_demorados = alt.Chart(top_10_demorados).mark_bar(
                color='#ff9800' # Naranja
            ).encode(
                x=alt.X('Cantidad', title='Número de Pendientes'),
                y=alt.Y('Destino', sort='-x', title='Destino'),
                tooltip=['Destino', 'Cantidad']
            ).properties(
                title='Top 10 Pendientes Acumulado'
            )
            st.altair_chart(chart_top_demorados, use_container_width=True)

# --- Lógica de Detección de Cambios y Notificaciones ---
# Compara el DataFrame antiguo con el nuevo para detectar cambios de estado
# y envía notificaciones a los tokens de FCM guardados.
def check_and_notify_on_change(old_df, new_df):
    try:
        st.session_state.messages.append({'type': 'warning', 'text': "⚠️ Iniciando detección de cambios..."})
        
        # Función auxiliar para limpiar y estandarizar DataFrames.
        def clean_dataframe(df):
            df_cleaned = df.copy()
            for col in ['Destino', 'Folio pedido', 'Producto', 'Estado de atención']:
                if col in df_cleaned.columns:
                    df_cleaned[col] = df_cleaned[col].astype(str).str.strip().str.upper()
            
            if 'Fecha' in df_cleaned.columns:
                df_cleaned['Fecha'] = pd.to_datetime(df_cleaned['Fecha'], errors='coerce').dt.strftime('%Y-%m-%d')
            
            return df_cleaned

        old_df_clean = clean_dataframe(old_df)
        new_df_clean = clean_dataframe(new_df)
        
        st.session_state.messages.append({'type': 'info', 'text': f"Diagnóstico - Filas en archivo antiguo: {len(old_df_clean)}"})
        st.session_state.messages.append({'type': 'info', 'text': f"Diagnóstico - Filas en archivo nuevo: {len(new_df_clean)}"})

        cambios_detectados = []
        comparison_key_columns = ['Destino', 'Folio pedido', 'Producto', 'Fecha']
        old_df_indexed = old_df_clean.set_index(comparison_key_columns)
        
        for index, row in new_df_clean.iterrows():
            try:
                key = (row['Destino'], row['Folio pedido'], row['Producto'], row['Fecha'])
                
                if key in old_df_indexed.index:
                    old_status = old_df_indexed.loc[key, 'Estado de atención']
                    new_status = row['Estado de atención']
                    
                    if old_status != new_status:
                        cambios_detectados.append({
                            'Destino': row['Destino'],
                            'Folio pedido': row['Folio pedido'],
                            'Fecha': row['Fecha'],
                            'Producto': row['Producto'],
                            'Estado de atención_old': old_status,
                            'Estado de atención_new': new_status
                        })
            except KeyError:
                pass

        cambios_df = pd.DataFrame(cambios_detectados)
        
        if not cambios_df.empty:
            st.session_state.messages.append({'type': 'info', 'text': f"🔍 Se detectaron {len(cambios_df)} cambios de estatus."})
            st.warning("🔔 Enviando notificaciones...")
            
            # Verifica si hay tokens de FCM guardados en la sesión.
            if 'fcm_tokens' not in st.session_state:
                st.session_state.fcm_tokens = {}
                st.warning("⚠️ No se encontraron tokens de FCM guardados para notificar.")
                return

            # Itera sobre los cambios detectados y envía una notificación por cada uno.
            for _, row in cambios_df.iterrows():
                destino = row['Destino']
                destino_num = str(destino).split('-')[0].strip().upper()
                
                # Si existe un token para este destino, envía la notificación.
                if destino_num in st.session_state.fcm_tokens:
                    token = st.session_state.fcm_tokens[destino_num]
                    estado_anterior = row['Estado de atención_old']
                    estado_nuevo = row['Estado de atención_new']
                    
                    titulo = f"Actualización en Destino: {destino}"
                    mensaje = f"Estado cambió de '{estado_anterior}' a '{estado_nuevo}'"
                    
                    enviar_notificacion_por_token(token, titulo, mensaje)
                else:
                    st.warning(f"No se encontró un token para el destino {destino_num}. No se enviará notificación.")
        else:
            st.session_state.messages.append({'type': 'success', 'text': "✅ No se detectaron cambios en el estado de los destinos."})
    except Exception as e:
        st.session_state.messages.append({'type': 'error', 'text': f"❌ Error en la lógica de notificación: {e}"})

# --- Panel de Administración ---
# Permite al administrador subir archivos Excel para actualizar la base de datos
# y ver el historial de actualizaciones y mensajes de la aplicación.
def admin_panel():
    st.title("📤 Subida de archivo Excel")

    if 'messages' not in st.session_state:
        st.session_state.messages = []

    col1, col2 = st.columns([3, 1])

    if 'last_df' not in st.session_state:
        st.session_state.last_df = pd.DataFrame()
        if os.path.exists(DB_PATH):
            try:
                st.session_state.last_df = cargar_datos()
            except Exception as e:
                st.session_state.messages.append({'type': 'error', 'text': f"Error al cargar la base de datos histórica: {e}"})
                st.session_state.last_df = pd.DataFrame()
                st.rerun()

    with col1:
        uploaded_file = st.file_uploader("Selecciona archivo (.xlsx)", type=["xlsx"])
        
        if os.path.exists(DB_PATH):
            file_size_bytes = os.path.getsize(DB_PATH)
            file_size_mb = file_size_bytes / (1024 * 1024)
            st.markdown(f"💾 **Tamaño actual de la base de datos:** {file_size_mb:.2f} MB")
            
        if uploaded_file is not None:
            try:
                df_nuevo = pd.read_excel(
                    uploaded_file,
                    engine='openpyxl',
                    sheet_name=0,
                    dtype={
                        'Destino': str,
                        'Fecha': 'datetime64[ns]',
                        'Producto': str,
                        'Folio pedido': str,
                        'Estado de atención': str
                    }
                )

                st.write("Vista previa del archivo cargado:")
                st.dataframe(df_nuevo.head())

                if st.button("Cargar y actualizar base histórica"):
                    st.session_state.messages = [] # Limpiar mensajes anteriores para la nueva acción
                    
                    df_historico_old = st.session_state.last_df.copy()

                    if not df_historico_old.empty:
                        check_and_notify_on_change(df_historico_old, df_nuevo)
                    
                    guardar_datos(df_nuevo)
                    st.session_state.last_df = df_nuevo.copy()

                    ahora = datetime.datetime.now(tz=cdmx_tz).isoformat()
                    guardar_historial(ahora)

                    st.session_state.messages.append({'type': 'success', 'text': "✅ Base de datos histórica actualizada. El archivo subido es la nueva base."})

                    st.cache_data.clear()
                    st.rerun()

            except Exception as e:
                st.session_state.messages.append({'type': 'error', 'text': f"❌ Error al procesar archivo: {e}"})
                st.rerun()
                
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
    
    # --- Historial de Mensajes Persistente ---
    st.markdown("---")
    st.subheader("📜 Historial de acciones")
    if st.session_state.messages:
        for i, msg_data in enumerate(st.session_state.messages):
            if msg_data['type'] == 'success':
                st.success(f"{i+1}. {msg_data['text']}")
            elif msg_data['type'] == 'error':
                st.error(f"{i+1}. {msg_data['text']}")
            elif msg_data['type'] == 'warning':
                st.warning(f"{i+1}. {msg_data['text']}")
            elif msg_data['type'] == 'info':
                st.info(f"{i+1}. {msg_data['text']}")
        if st.button("Limpiar historial"):
            st.session_state.messages = []
            st.rerun()
    else:
        st.info("No hay acciones recientes.")
    # --- Fin del Historial de Mensajes ---

    admin_dashboard()
    
    if st.button("Cerrar sesión"):
        st.session_state.logged_in = False
        st.session_state.last_df = pd.DataFrame()
        st.session_state.messages = []
        st.rerun()
            
    st.markdown("---")
    st.header("⚠️ Opciones de mantenimiento")
    if st.button("🔴 Reiniciar base de datos", help="Borra todos los archivos de historial para empezar de cero."):
        
        archivos_a_borrar = [DB_PATH, HISTORIAL_PATH]
        
        borrados = 0
        for archivo in archivos_a_borrar:
            if os.path.exists(archivo):
                os.remove(archivo)
                borrados += 1
                st.session_state.messages.append({'type': 'success', 'text': f"🗑️ Archivo '{archivo}' eliminado."})
            else:
                st.session_state.messages.append({'type': 'info', 'text': f"Archivo '{archivo}' no encontrado."})
        
        st.session_state.messages.append({'type': 'warning', 'text': f"¡Se han eliminado {borrados} archivos! La base de datos se ha reiniciado por completo."})
        st.session_state.messages.append({'type': 'info', 'text': "Ahora la aplicación está en un estado 'de fábrica'. Por favor, sube tu primer archivo Excel para comenzar un nuevo historial limpio."})
        
        st.cache_data.clear()
        st.rerun()

# --- Función para Mostrar Fichas Visuales ---
# Genera y muestra tarjetas visuales para cada fila de datos de destino.
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

        destino = fila.get('Destino', '')
        fecha_general = fila.get('Fecha', None)

        if pd.notnull(fecha_general):
            try:
                fecha_general = pd.to_datetime(fecha_general).strftime('%d/%m/%Y')
            except (ValueError, TypeError):
                fecha_general = str(fecha_general)

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
                <b>Estado:</b> {estado}<br>
            </div>
        </div>
        """
        st.markdown(ficha_html, unsafe_allow_html=True)

# --- Panel de Usuario ---
# Permite a los usuarios consultar el estado de un destino específico y suscribirse a notificaciones.
def user_panel():
    st.title("🔍 Consulta de Estatus")

    if not os.path.exists(DB_PATH):
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
            st.info("📅 Última actualización: (sin datos)")
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
    if 'Fecha' not in df.columns:
        st.error("❌ Falta la columna 'Fecha' para ordenar por día.")
        return

    pedido = st.text_input("Ingresa tu número de destino")
    if pedido:
        columnas = ['Destino', 'Fecha', 'Producto', 'Turno', 'Capacidad programada (Litros)',
                    'Fecha y hora estimada', 'Fecha y hora de facturación', 'Estado de atención']
        columnas_validas = [col for col in columnas if col in df.columns]

        df['Destino_num'] = df['Destino'].astype(str).str.split('-').str[0].str.strip()
        df['Destino'] = df['Destino'].astype(str).str.strip().str.upper()

        resultado = df[df['Destino_num'] == pedido.strip()]
        
        if not resultado.empty:
            destino_num_para_suscripcion = str(resultado['Destino_num'].iloc[0]).strip().upper()
            
            # --- Sección de Suscripción a Notificaciones de Firebase ---
            st.markdown(f"""
                ---
                ### Suscripción a notificaciones del Destino {destino_num_para_suscripcion}
                
                **Paso 1:** Permite las notificaciones de este sitio en tu navegador cuando te lo pregunte.
                
                **Paso 2:** Haz clic en el botón de abajo y revisa la **consola del navegador (F12)**. El token de suscripción aparecerá ahí y en una alerta.
            """)
            
            if st.button(f"🔔 Obtener mi token para Destino {destino_num_para_suscripcion}", key="get_token"):
                st.info("Copia el token que se mostró en la consola y pégalo en el campo siguiente.")
                
            st.markdown("---")
            fcm_token = st.text_input("Pega tu Token de FCM aquí:", key="fcm_token_input")
            
            if fcm_token:
                # Guarda el token en el estado de la sesión de Streamlit para que el backend pueda usarlo.
                if 'fcm_tokens' not in st.session_state:
                    st.session_state.fcm_tokens = {}
                st.session_state.fcm_tokens[destino_num_para_suscripcion] = fcm_token
                st.success(f"✅ Token guardado. Ahora recibirás notificaciones para el destino **{destino_num_para_suscripcion}**.")
            
            # --- Fin de la Sección de Suscripción ---
            
            if not resultado.empty:
                mostrar_fichas_visuales(resultado)
            else:
                st.warning("No se encontró ningún destino con ese número.")
                if 'last_df' in st.session_state and not st.session_state.last_df.empty:
                    st.markdown("---")
                    st.subheader("Búsqueda en base histórica")
                    df_historico = st.session_state.last_df
                    df_historico['Destino_num'] = df_historico['Destino'].astype(str).str.split('-').str[0].str.strip()
                    resultado_historico = df_historico[df_historico['Destino_num'] == pedido.strip()]
                    if not resultado_historico.empty:
                        st.markdown("Hemos encontrado este destino en nuestra base de datos, pero no está activo en el archivo más reciente:")
                        mostrar_fichas_visuales(resultado_historico)
                    else:
                        st.info("No se encontró este destino en la base de datos histórica.")

# --- Lógica Principal de la Aplicación ---
# Controla el flujo de la aplicación, mostrando el panel de usuario o el panel de administración
# dependiendo del estado de inicio de sesión.
def main():
    pwa_setup()
    fcm_pwa_setup() # Llama a la función que configura Firebase y PWA en el frontend.

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if st.session_state.logged_in:
        st.sidebar.title("Menú")
        opcion = st.sidebar.radio("Elige una opción:", ["Panel de administración", "Dashboard de datos", "Cerrar sesión"])
        if opcion == "Panel de administración":
            admin_panel()
        elif opcion == "Dashboard de datos":
            admin_dashboard()
        elif opcion == "Cerrar sesión":
            st.session_state.logged_in = False
            st.session_state.last_df = pd.DataFrame()
            st.session_state.messages = []
            st.rerun()
    else:
        st.sidebar.title("Menú")
        opcion = st.sidebar.radio("Elige una opción:", ["Consulta", "Administrador"])
        if opcion == "Consulta":
            user_panel()
        elif opcion == "Administrador":
            login()

# --- Punto de Entrada de la Aplicación ---
# Asegura que la función 'main' se ejecute cuando el script es iniciado.
if __name__ == "__main__":
    main()
