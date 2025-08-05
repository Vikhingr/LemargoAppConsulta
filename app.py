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

    st.subheader("📊 Visualización y análisis de datos")

    columnas_disponibles = df.columns.tolist()

    if 'Fecha' in columnas_disponibles:
        df['Fecha'] = pd.to_datetime(df['Fecha']).dt.date
    else:
        st.warning("La columna 'Fecha' no se encontró en el archivo. No se podrá filtrar por fecha.")
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

    # --- DATOS FILTRADOS POR FECHA (PARA GRÁFICAS DIARIAS) ---
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


    # --- ANÁLISIS HISTÓRICO ACUMULADO (TOP 10) ---
    st.markdown("---")
    st.subheader("🏆 Análisis histórico - Top 10 Destinos")
    st.info("Estas gráficas se basan en **todos los datos del archivo histórico**.")

    # Aseguramos que las columnas necesarias existan en el DataFrame completo
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


# --- Lógica de notificaciones mejorada (ahora compara por Destino, Fecha y Producto) ---
def check_and_notify_on_change(old_df, new_df):
    try:
        st.warning("⚠️ Iniciando detección de cambios...")
        
        # Estandarizar las columnas clave de ambos DataFrames de forma estricta
        def clean_dataframe(df):
            df_cleaned = df.copy()
            for col in ['Destino', 'Producto', 'Estado de atención']:
                if col in df_cleaned.columns:
                    df_cleaned[col] = df_cleaned[col].astype(str).str.strip().str.upper()
            
            if 'Fecha' in df_cleaned.columns:
                df_cleaned['Fecha'] = pd.to_datetime(df_cleaned['Fecha'], errors='coerce').dt.strftime('%Y-%m-%d')
            
            return df_cleaned

        old_df_clean = clean_dataframe(old_df)
        new_df_clean = clean_dataframe(new_df)
        
        st.info(f"Diagnóstico - Filas en archivo antiguo: {len(old_df_clean)}")
        st.info(f"Diagnóstico - Filas en archivo nuevo: {len(new_df_clean)}")

        # --- LÓGICA FINAL Y A PRUEBA DE ERRORES ---
        cambios_detectados = []
        
        # Usar un diccionario para una búsqueda rápida en el DataFrame antiguo
        old_data_dict = old_df_clean.set_index(['Destino', 'Fecha', 'Producto']).to_dict('index')

        for index, row in new_df_clean.iterrows():
            key = (row['Destino'], row['Fecha'], row['Producto'])
            
            if key in old_data_dict:
                old_row = old_data_dict[key]
                if old_row['Estado de atención'] != row['Estado de atención']:
                    cambios_detectados.append({
                        'Destino': row['Destino'],
                        'Fecha': row['Fecha'],
                        'Producto': row['Producto'],
                        'Estado de atención_old': old_row['Estado de atención'],
                        'Estado de atención_new': row['Estado de atención']
                    })

        cambios_df = pd.DataFrame(cambios_detectados)
        
        if not cambios_df.empty:
            st.header("🔍 Cambios de estatus detectados")
            st.info(f"Se detectaron {len(cambios_df)} cambios de estatus. Aquí está la tabla de cambios:")
            st.dataframe(cambios_df)

            st.warning("🔔 Enviando notificaciones...")
            
            for _, row in cambios_df.iterrows():
                destino = row['Destino']
                estado_anterior = row['Estado de atención_old']
                estado_nuevo = row['Estado de atención_new']
                
                destino_num = str(destino).split('-')[0].strip()
                titulo = f"Actualización en Destino: {destino}"
                mensaje = f"Estado cambió de '{estado_anterior}' a '{estado_nuevo}'"
                enviar_notificacion_por_destino(destino_num, titulo, mensaje)
        else:
            st.info("✅ No se detectaron cambios en el estado de los destinos. No se enviaron notificaciones.")
            
    except Exception as e:
        st.error(f"Error en la lógica de notificación: {e}")

# --- NUEVA FUNCIÓN DE ADMINISTRADOR MÁS ROBUSTA ---
def admin_panel():
    st.title("📤 Subida de archivo Excel")

    col1, col2 = st.columns([3, 1])

    if 'last_df' not in st.session_state:
        st.session_state.last_df = pd.DataFrame()
        if os.path.exists(HISTORIAL_EXCEL_PATH):
            try:
                st.session_state.last_df = pd.read_excel(HISTORIAL_EXCEL_PATH)
            except Exception as e:
                st.error(f"Error al cargar el archivo histórico: {e}")
                st.session_state.last_df = pd.DataFrame()

    with col1:
        uploaded_file = st.file_uploader("Selecciona archivo (.xlsx)", type=["xlsx"])
        
        if os.path.exists(HISTORIAL_EXCEL_PATH):
            file_size_bytes = os.path.getsize(HISTORIAL_EXCEL_PATH)
            file_size_mb = file_size_bytes / (1024 * 1024)
            st.markdown(f"💾 **Tamaño actual de la base de datos:** {file_size_mb:.2f} MB")
            
        if uploaded_file is not None:
            try:
                df_nuevo = pd.read_excel(uploaded_file)
                st.write("Vista previa del archivo cargado:")
                st.dataframe(df_nuevo.head())

                if st.button("Cargar y actualizar base histórica"):
                    
                    df_historico_old = st.session_state.last_df.copy()

                    if not df_historico_old.empty:
                        check_and_notify_on_change(df_historico_old, df_nuevo)
                    
                    # --- NUEVA LÓGICA MÁS SIMPLE Y ROBUSTA ---
                    # Simplemente reemplazamos el archivo viejo con el nuevo
                    df_nuevo.to_excel(HISTORIAL_EXCEL_PATH, index=False)
                    st.session_state.last_df = df_nuevo.copy()

                    ahora = datetime.datetime.now(tz=cdmx_tz).isoformat()
                    guardar_historial(ahora)

                    st.success("✅ Base de datos histórica actualizada. El archivo subido es la nueva base.")
                    st.cache_data.clear()

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
        st.session_state.last_df = pd.DataFrame()
        try:
            st.experimental_rerun()
        except AttributeError:
            st.rerun()
            
    st.markdown("---")
    st.header("⚠️ Opciones de mantenimiento")
    if st.button("🔴 Reiniciar base de datos", help="Borra todos los archivos de historial para empezar de cero."):
        
        archivos_a_borrar = [HISTORIAL_EXCEL_PATH, HISTORIAL_PATH, HASH_PATH]
        
        borrados = 0
        for archivo in archivos_a_borrar:
            if os.path.exists(archivo):
                os.remove(archivo)
                borrados += 1
                st.success(f"🗑️ Archivo '{archivo}' eliminado.")
            else:
                st.info(f"Archivo '{archivo}' no encontrado.")
        
        st.warning(f"¡Se han eliminado {borrados} archivos! La base de datos se ha reiniciado por completo.")
        st.info("Ahora la aplicación está en un estado 'de fábrica'. Por favor, sube tu primer archivo Excel para comenzar un nuevo historial limpio.")
        st.cache_data.clear()
        
        try:
            st.experimental_rerun()
        except AttributeError:
            st.rerun()


# --- Función para mostrar fichas visuales (SIN el botón) ---
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
                <b>Estado:</b> {estado}
            </div>
        </div>
        """
        st.markdown(ficha_html, unsafe_allow_html=True)


# --- Panel de usuario corregido para mostrar por día y suscribir por número ---
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
            destino_para_suscripcion = resultado['Destino'].iloc[0]
            destino_num_para_suscripcion = str(destino_para_suscripcion).split('-')[0].strip().upper()

            descripcion = f"Suscríbete para recibir notificaciones sobre cualquier cambio en el estatus del Destino {destino_num_para_suscripcion}. Las notificaciones se enviarán automáticamente solo cuando haya una actualización."
            st.info(descripcion)

            if st.button(f"🔔 Suscribirme al Destino {destino_num_para_suscripcion}", key=f"sub_{destino_num_para_suscripcion}"):

                st.success(f"¡Suscripción exitosa! Ahora recibirás notificaciones para el Destino {destino_num_para_suscripcion}.")

                st.markdown(f"""
                <script>
                window.OneSignal = window.OneSignal || [];
                OneSignal.push(function() {{
                    OneSignal.isPushNotificationsEnabled(function(isEnabled) {{
                        if (isEnabled) {{
                            OneSignal.sendTags({{
                                destino_id: "{destino_num_para_suscripcion}"
                            }}).then(function(tags) {{
                                console.log('Suscrito al destino:', tags);
                            }});
                        }} else {{
                            OneSignal.showSlidedownPrompt();
                            alert('Por favor, activa las notificaciones para poder suscribirte.');
                        }}
                    }});
                }});
                </script>
                """, unsafe_allow_html=True)
                try:
                    st.experimental_rerun()
                except AttributeError:
                    st.rerun()

            resultado = resultado[columnas_validas].sort_values(by='Fecha', ascending=False)

            for fecha, grupo in resultado.groupby('Fecha'):
                fecha_formateada = pd.to_datetime(fecha).strftime('%d/%m/%Y')
                st.subheader(f"📅 Detalles del día: {fecha_formateada}")
                mostrar_fichas_visuales(grupo)
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
