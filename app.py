import streamlit as st
import os
import pandas as pd
import requests
import datetime
import json
import hashlib
import altair as alt
import matplotlib.pyplot as plt
import io

# --- OneSignal Config desde secrets ---
APP_ID = st.secrets.get("ONESIGNAL_APP_ID")
REST_API_KEY = st.secrets.get("ONESIGNAL_REST_API_KEY")

# --- Credenciales admin desde secrets ---
ADMIN_USER = st.secrets.get("ADMIN_USER")
ADMIN_PASS = st.secrets.get("ADMIN_PASS")

# --- Rutas y archivos ---
EXCEL_PATH = "archivo_cargado.xlsx"
HISTORIAL_ACTUALIZACIONES = "historial_actualizaciones.json"
HASH_PATH = "hash_actual.txt"
HISTORICO_ESTATUS_PATH = "historico_estatus.xlsx"

# --- PWA Setup ---
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

# --- OneSignal Web Push Setup ---
def onesignal_web_push_setup():
    if not APP_ID:
        st.error("❌ APP_ID de OneSignal no configurado en secrets.")
        return
    st.markdown(f"""
    <script>
    (function() {{
        function loadOneSignalSDK(callback) {{
            var script = document.createElement('script');
            script.src = "https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.js";
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
                    allowLocalhostAsSecureOrigin: true
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

# --- Enviar notificación OneSignal ---
def enviar_notificacion(titulo, mensaje, segmento=None):
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
        "headings": {"en": titulo},
        "contents": {"en": mensaje},
        "ios_sound": "default",
        "android_sound": "default",
    }
    if segmento:
        payload["include_external_user_ids"] = [segmento]
    else:
        payload["included_segments"] = ["All"]
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        st.success("✅ Notificación enviada")
    except requests.RequestException as e:
        st.error(f"❌ Error al enviar notificación: {e}")

# --- Historial de cargas ---
def cargar_historial_actualizaciones():
    if os.path.exists(HISTORIAL_ACTUALIZACIONES):
        try:
            with open(HISTORIAL_ACTUALIZACIONES, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def guardar_historial_actualizacion(fecha_hora):
    historial = cargar_historial_actualizaciones()
    historial.append(fecha_hora)
    try:
        with open(HISTORIAL_ACTUALIZACIONES, "w") as f:
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

# --- Cargar datos con cache ---
@st.cache_data(show_spinner=False)
def cargar_datos():
    if not os.path.exists(EXCEL_PATH):
        return pd.DataFrame()
    return pd.read_excel(EXCEL_PATH)

# --- Cargar histórico estatus ---
@st.cache_data(show_spinner=False)
def cargar_historico():
    if not os.path.exists(HISTORICO_ESTATUS_PATH):
        columnas = [
            "Fecha Pedido", "Folio Pedido", "Centro de entrega", "Destino", "Producto",
            "Presentación", "Turno", "Medio", "Clave", "Transportista",
            "Capacidad programada (Litros)", "Fecha y hora estimada",
            "Fecha y hora de facturación", "Estado de atención", "Timestamp de actualización", "ID_UNICO"
        ]
        return pd.DataFrame(columns=columnas)
    return pd.read_excel(HISTORICO_ESTATUS_PATH)

# --- Actualizar histórico y enviar notificaciones por destino ---
def actualizar_historico_desde_archivo():
    if not os.path.exists(EXCEL_PATH):
        st.warning("No hay archivo base cargado para procesar.")
        return

    try:
        df_nuevo = pd.read_excel(EXCEL_PATH)
    except Exception as e:
        st.error(f"Error leyendo archivo cargado: {e}")
        return

    required_columns = [
        "Fecha", "Destino", "Estado de atención", "Folio Pedido",
        "Centro de entrega", "Producto", "Presentación", "Turno", "Medio",
        "Clave", "Transportista", "Capacidad programada (Litros)",
        "Fecha y hora estimada", "Fecha y hora de facturación"
    ]
    missing = [c for c in required_columns if c not in df_nuevo.columns]
    if missing:
        st.error(f"Faltan columnas obligatorias en el archivo: {missing}")
        return

    df_nuevo["Fecha Pedido"] = pd.to_datetime(df_nuevo["Fecha"]).dt.date.astype(str)
    df_nuevo["Timestamp de actualización"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df_nuevo["ID_UNICO"] = df_nuevo["Destino"].astype(str) + "_" + df_nuevo["Fecha Pedido"].astype(str)

    columnas_historico = [
        "Fecha Pedido", "Folio Pedido", "Centro de entrega", "Destino", "Producto",
        "Presentación", "Turno", "Medio", "Clave", "Transportista",
        "Capacidad programada (Litros)", "Fecha y hora estimada",
        "Fecha y hora de facturación", "Estado de atención", "Timestamp de actualización", "ID_UNICO"
    ]
    df_nuevo = df_nuevo[columnas_historico]

    df_hist = cargar_historico()

    cambios_detectados = []
    for id_unico, grupo in df_nuevo.groupby("ID_UNICO"):
        nuevo_registro = grupo.sort_values("Timestamp de actualización", ascending=False).iloc[0]
        estatus_nuevo = nuevo_registro["Estado de atención"]
        prev = df_hist[df_hist["ID_UNICO"] == id_unico]

        if prev.empty:
            df_hist = pd.concat([df_hist, pd.DataFrame([nuevo_registro])], ignore_index=True)
            cambios_detectados.append((id_unico, None, estatus_nuevo))
        else:
            ultimo_prev = prev.sort_values("Timestamp de actualización", ascending=False).iloc[0]
            estatus_prev = ultimo_prev["Estado de atención"]
            if estatus_prev != estatus_nuevo:
                df_hist = pd.concat([df_hist, pd.DataFrame([nuevo_registro])], ignore_index=True)
                cambios_detectados.append((id_unico, estatus_prev, estatus_nuevo))

    try:
        df_hist.to_excel(HISTORICO_ESTATUS_PATH, index=False)
    except Exception as e:
        st.error(f"Error guardando histórico: {e}")
        return

    # Enviar notificaciones personalizadas por destino (sin registro, usa external_user_id = destino)
    if cambios_detectados:
        resumen = []
        destinos_notificados = set()
        for id_unico, antes, despues in cambios_detectados:
            destino, fecha = id_unico.split("_", 1)
            destinos_notificados.add(destino)
            if antes is None:
                resumen.append(f"{destino} ({fecha}): nuevo estatus '{despues}'")
            else:
                resumen.append(f"{destino} ({fecha}): '{antes}' → '{despues}'")
        mensaje = "Cambios detectados:\n" + "\n".join(resumen[:5])
        if len(resumen) > 5:
            mensaje += f"\n... y {len(resumen)-5} más."
        st.info("Enviando notificaciones a destinos afectados...")
        for destino in destinos_notificados:
            enviar_notificacion("Actualización de estatus", mensaje, segmento=destino)
    else:
        st.info("No se detectaron cambios en estatus respecto al histórico.")

# --- Login ---
def login():
    st.title("🔐 Login Administrador")
    st.markdown("""
    <style>
    .login-container {
        position: fixed;
        top: 50px;
        right: 20px;
        width: 250px;
        background-color: #1e1e2f;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 0 10px #00000088;
    }
    .login-container input {
        background-color: #33334d;
        color: #eee;
        border: none;
        padding: 8px;
        margin-bottom: 10px;
        width: 100%;
        border-radius: 5px;
    }
    .login-container button {
        width: 100%;
        background-color: #556cd6;
        color: white;
        border: none;
        padding: 10px;
        border-radius: 5px;
        cursor: pointer;
    }
    .login-container button:hover {
        background-color: #4051b5;
    }
    </style>
    """, unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        user = st.text_input("Usuario", key="user_input")
        pwd = st.text_input("Contraseña", type="password", key="pwd_input")
        if st.button("Entrar", key="login_button"):
            if user == ADMIN_USER and pwd == ADMIN_PASS:
                st.session_state.logged_in = True
                try:
                    st.experimental_rerun()
                except AttributeError:
                    st.rerun()
            else:
                st.error("❌ Usuario o contraseña incorrectos")
        st.markdown('</div>', unsafe_allow_html=True)

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

    st.subheader("📊 Visualización de datos actuales")

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

# Mostrar gráfico histórico por destino
    df_hist = cargar_historico()
    if df_hist.empty:
        st.info("No hay datos históricos para mostrar.")
    else:
        destinos = df_hist["Destino"].unique().tolist()
        destino_sel = st.selectbox("Selecciona destino para gráfico histórico", destinos)
        if destino_sel:
            df_destino = df_hist[df_hist["Destino"] == destino_sel].copy()
            if df_destino.empty:
                st.warning("No hay datos para este destino.")
            else:
                df_destino["Fecha Pedido"] = pd.to_datetime(df_destino["Fecha Pedido"])
                pivot = df_destino.groupby("Fecha Pedido")["Estado de atención"].value_counts().unstack().fillna(0)
                st.subheader(f"📈 Evolución de estados para {destino_sel}")
                try:
                    fig, ax = plt.subplots(figsize=(10,4))
                    pivot.plot(kind="bar", stacked=True, ax=ax)
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    st.pyplot(fig)
                except Exception as e:
                    st.error(f"Error al generar gráfico: {e}")

# --- Panel Admin ---
def admin_panel():
    st.title("📤 Subida de archivo Excel y actualización de histórico")
    col1, col2 = st.columns([3, 1])

    with col1:
        uploaded_file = st.file_uploader("Selecciona archivo Excel (.xlsx)", type=["xlsx"])
        if uploaded_file is not None:
            try:
                with open(EXCEL_PATH, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                nuevo_hash = calcular_hash_archivo()
                hash_guardado = cargar_hash_guardado()

                if nuevo_hash != hash_guardado:
                    guardar_hash_actual(nuevo_hash)
                    ahora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    guardar_historial_actualizacion(ahora)
                    st.success("Archivo cargado correctamente. Ahora actualiza el histórico.")
                else:
                    st.info("Archivo idéntico al cargado previamente. No se actualizó.")

                try:
                    st.experimental_rerun()
                except AttributeError:
                    st.rerun()
            except Exception as e:
                st.error(f"Error al guardar archivo: {e}")

    with col2:
        with st.expander("📅 Historial de actualizaciones"):
            historial = cargar_historial_actualizaciones()
            if historial:
                for i, fecha in enumerate(historial[::-1], 1):
                    st.write(f"{i}. {fecha}")
            else:
                st.write("No hay actualizaciones registradas.")

    if st.button("Actualizar historial"):
        actualizar_historico_desde_archivo()

    admin_dashboard()

    if st.button("Cerrar sesión"):
        st.session_state.logged_in = False
        try:
            st.experimental_rerun()
        except AttributeError:
            st.rerun()

# --- Panel Usuario ---
def user_panel():
    st.title("🔍 Consulta de Estatus")

    if not os.path.exists(EXCEL_PATH):
        st.info("Esperando que el administrador suba un archivo para consulta.")
        return

    timestamp = os.path.getmtime(EXCEL_PATH)
    ultima_mod = datetime.datetime.fromtimestamp(timestamp)
    st.info(f"📅 Última actualización: {ultima_mod.strftime('%d/%m/%Y - %H:%M Hrs.')}")

    try:
        df = cargar_datos()
    except Exception as e:
        st.error(f"Error al leer archivo: {e}")
        return

    if df.empty:
        st.info("Archivo cargado pero sin datos.")
        return

    if 'Destino' not in df.columns:
        st.error("❌ Falta la columna 'Destino' en el archivo.")
        return

    destino_input = st.text_input("Ingresa tu número de destino para consulta:")
    fecha_input = st.date_input("Filtrar por fecha (opcional):")

    if destino_input:
        if len(destino_input) < 3:
            st.info("Escribe al menos 3 caracteres para buscar.")
            return

        df_filtered = df[df['Destino'].astype(str).str.contains(destino_input, case=False)]

        if fecha_input:
            try:
                fecha_str = fecha_input.strftime("%Y-%m-%d")
                df_filtered["Fecha"] = pd.to_datetime(df_filtered["Fecha"]).dt.strftime("%Y-%m-%d")
                df_filtered = df_filtered[df_filtered["Fecha"] == fecha_str]
            except Exception:
                pass

        columnas_mostrar = ['Destino', 'Producto', 'Turno', 'Capacidad programada (Litros)',
                            'Fecha y hora estimada', 'Fecha y hora de facturación', 'Estado de atención']
        columnas_validas = [col for col in columnas_mostrar if col in df_filtered.columns]

        resultado = df_filtered[columnas_validas].reset_index(drop=True)

        if not resultado.empty:
            st.dataframe(resultado.style.set_properties(**{'text-align': 'center'}))
        else:
            st.warning("No se encontraron resultados para esa búsqueda.")

# --- App principal ---
def main():
    st.set_page_config(page_title="App de Pedidos Lemargo", layout="wide", initial_sidebar_state="expanded")
    pwa_setup()
    onesignal_web_push_setup()

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
