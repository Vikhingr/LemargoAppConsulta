import streamlit as st
import pandas as pd
import os
import datetime
import requests
import matplotlib.pyplot as plt

# --- Cargar secretos ---
ONESIGNAL_APP_ID = st.secrets["ONESIGNAL_APP_ID"]
ONESIGNAL_REST_API_KEY = st.secrets["ONESIGNAL_REST_API_KEY"]
ADMIN_USER = st.secrets["ADMIN_USER"]
ADMIN_PASS = st.secrets["ADMIN_PASS"]

# --- Configuración visual dark ---
st.set_page_config(page_title="Seguimiento de Pedidos", layout="wide", page_icon="📦")
st.markdown("""
    <style>
    body, .stApp {
        background-color: #121212;
        color: #e0e0e0;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .css-18e3th9 {
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-left: 3rem;
        padding-right: 3rem;
    }
    .stTextInput>div>div>input {
        background-color: #222;
        color: #e0e0e0;
        border-radius: 6px;
        padding: 8px;
        border: 1px solid #444;
    }
    .stButton>button {
        background-color: #2962ff;
        color: white;
        border-radius: 8px;
        padding: 8px 20px;
        font-weight: 600;
        transition: background-color 0.3s ease;
        border: none;
        margin-top: 10px;
    }
    .stButton>button:hover {
        background-color: #0039cb;
        cursor: pointer;
    }
    .stSelectbox>div>div>div {
        background-color: #222;
        color: #e0e0e0;
        border-radius: 6px;
    }
    .css-1aumxhk {
        background-color: #222 !important;
        border-radius: 6px !important;
    }
    .css-1kyxreq {
        background-color: #222 !important;
        border-radius: 6px !important;
    }
    .css-1v0mbdj {
        background-color: #222 !important;
        border-radius: 6px !important;
    }
    .css-1r6slb0 {
        border-radius: 6px !important;
    }
    .stDownloadButton>button {
        background-color: #4caf50;
        color: white;
        border-radius: 8px;
        padding: 8px 20px;
        font-weight: 600;
        margin-top: 10px;
        border: none;
    }
    .stDownloadButton>button:hover {
        background-color: #357a38;
        cursor: pointer;
    }
    .stAlert {
        background-color: #2a2a2a !important;
        color: #ffa500 !important;
        border-radius: 8px;
        padding: 12px;
    }
    </style>
""", unsafe_allow_html=True)

# --- Función para enviar notificaciones OneSignal a un destino ---
def enviar_notificacion(destino, mensaje):
    url = "https://onesignal.com/api/v1/notifications"
    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "filters": [{"field": "tag", "key": "destino", "relation": "=", "value": destino}],
        "contents": {"en": mensaje},
        "ios_sound": "default",
        "android_sound": "default"
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {ONESIGNAL_REST_API_KEY}"
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        st.success("✅ Notificación enviada correctamente")
    except Exception as e:
        st.error(f"❌ Error enviando notificación: {e}")

# --- Actualizar base y detectar cambios ---
def actualizar_base(nuevo_df):
    nuevo_df["ID"] = nuevo_df["Destino"] + "_" + nuevo_df["Fecha"].astype(str)
    nuevo_df["Hora de consulta"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nuevo_df["Fuente"] = "Carga manual"

    if os.path.exists("historico_estatus.xlsx"):
        historico_df = pd.read_excel("historico_estatus.xlsx")
    else:
        historico_df = pd.DataFrame(columns=nuevo_df.columns)

    historico_df["ID"] = historico_df["Destino"] + "_" + historico_df["Fecha"].astype(str)
    df_combinado = pd.concat([historico_df, nuevo_df], ignore_index=True)
    df_final = df_combinado.drop_duplicates(subset="ID", keep="last")

    cambios = []
    for _, fila in nuevo_df.iterrows():
        id_registro = fila["ID"]
        nuevo_estatus = fila["Estado de atención"]
        if id_registro in historico_df["ID"].values:
            viejo_estatus = historico_df.loc[historico_df["ID"] == id_registro, "Estado de atención"].values[0]
            if nuevo_estatus != viejo_estatus:
                cambios.append((fila["Destino"], viejo_estatus, nuevo_estatus))
        else:
            # Nuevo registro sin historial previo
            cambios.append((fila["Destino"], None, nuevo_estatus))

    df_final.to_excel("historico_estatus.xlsx", index=False)

    for destino, viejo, nuevo in cambios:
        if viejo is None:
            mensaje = f"Tu pedido para destino '{destino}' tiene estatus: '{nuevo}' (nuevo registro)"
        else:
            mensaje = f"Tu pedido cambió de '{viejo}' a '{nuevo}'"
        enviar_notificacion(destino, mensaje)

# --- Estado de suscripción OneSignal en JS (envía mensaje a Streamlit) ---
SUSCRIPCION_JS = """
<script>
window.OneSignal = window.OneSignal || [];
OneSignal.push(function() {
    OneSignal.init({
        appId: "%s",
        notifyButton: {
            enable: false
        }
    });
    OneSignal.isPushNotificationsEnabled(function(isEnabled) {
        if (isEnabled) {
            OneSignal.getUserId(function(userId) {
                window.parent.postMessage({type: "onesignal_status", status: "subscribed", userId: userId}, "*");
            });
        } else {
            window.parent.postMessage({type: "onesignal_status", status: "unsubscribed"}, "*");
        }
    });
});
</script>
""" % ONESIGNAL_APP_ID

# --- Panel Admin ---
def admin_panel():
    st.header("🛠️ Panel Administrador")
    archivo = st.file_uploader("Subir archivo Excel con nuevos datos", type=["xlsx"])
    if archivo is not None:
        with open("nuevo_datos.xlsx", "wb") as f:
            f.write(archivo.getbuffer())
        st.success("Archivo cargado correctamente.")

    if st.button("Actualizar Base con nuevo archivo"):
        if os.path.exists("nuevo_datos.xlsx"):
            try:
                df_nuevo = pd.read_excel("nuevo_datos.xlsx")
                actualizar_base(df_nuevo)
                st.success("Base actualizada y notificaciones enviadas.")
            except Exception as e:
                st.error(f"Error al actualizar base: {e}")
        else:
            st.warning("No hay archivo nuevo_datos.xlsx cargado.")

    # Mostrar historial básico
    if os.path.exists("historico_estatus.xlsx"):
        st.markdown("### Vista previa del histórico")
        try:
            df_hist = pd.read_excel("historico_estatus.xlsx")
            st.dataframe(df_hist.tail(10))
        except:
            st.warning("No se pudo cargar el histórico para vista previa.")
    else:
        st.info("Aún no hay histórico creado.")

# --- Función para controlar suscripción via JS en usuario ---
def suscripcion_usuario(destino):
    st.markdown(f"""
    <script src="https://cdn.onesignal.com/sdks/OneSignalSDK.js" async=""></script>
    <script>
    window.OneSignal = window.OneSignal || [];
    OneSignal.push(function() {{
        OneSignal.init({{
            appId: "{ONESIGNAL_APP_ID}",
            notifyButton: {{
                enable: false
            }}
        }});
    }});

    const destino = "{destino}";

    function suscribir() {{
        OneSignal.push(function() {{
            OneSignal.sendTag("destino", destino).then(() => {{
                alert("Suscripción al destino '" + destino + "' exitosa.");
                window.location.reload();
            }});
        }});
    }}

    function cancelarSuscripcion() {{
        OneSignal.push(function() {{
            OneSignal.deleteTag("destino").then(() => {{
                alert("Suscripción cancelada.");
                window.location.reload();
            }});
        }});
    }}

    // Comprobar estado actual de suscripción
    OneSignal.push(function() {{
        OneSignal.getTags().then(function(tags) {{
            if(tags.destino === destino) {{
                document.getElementById("estadoSuscripcion").innerText = "🔔 Suscrito a: " + destino;
                document.getElementById("btnSuscribir").style.display = "none";
                document.getElementById("btnCancelar").style.display = "inline-block";
            }} else {{
                document.getElementById("estadoSuscripcion").innerText = "🔕 No suscrito";
                document.getElementById("btnSuscribir").style.display = "inline-block";
                document.getElementById("btnCancelar").style.display = "none";
            }}
        }});
    }});
    </script>

    <div style="margin-top:10px; margin-bottom:10px;">
        <span id="estadoSuscripcion" style="font-weight: 600;"></span><br>
        <button id="btnSuscribir" onclick="suscribir()" style="background-color:#2962ff; color:white; border:none; padding:8px 18px; border-radius:6px; cursor:pointer;">Suscribirme</button>
        <button id="btnCancelar" onclick="cancelarSuscripcion()" style="background-color:#b00020; color:white; border:none; padding:8px 18px; border-radius:6px; cursor:pointer; display:none;">Cancelar Suscripción</button>
    </div>
    """, unsafe_allow_html=True)

# --- Panel Usuario ---
def user_panel():
    st.header("🔍 Consulta de Estatus de Pedidos")

    if not os.path.exists("historico_estatus.xlsx"):
        st.warning("Aún no hay datos disponibles. Espera a que el administrador cargue la base.")
        return

    try:
        df_hist = pd.read_excel("historico_estatus.xlsx")
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return

    # Búsqueda texto libre de destino (min 3 caracteres)
    busqueda = st.text_input("Busca tu destino por texto (mínimo 3 caracteres)")
    destinos_disponibles = sorted(df_hist["Destino"].dropna().unique())

    df_filtrado = pd.DataFrame()
    destino_seleccionado = None

    if len(busqueda) >= 3:
        df_filtrado = df_hist[df_hist["Destino"].str.contains(busqueda, case=False, na=False)]
        if df_filtrado.empty:
            st.info("No se encontró ningún destino con ese texto.")
            return

        # Mostrar destinos filtrados para que el usuario confirme
        opciones = sorted(df_filtrado["Destino"].unique())
        destino_seleccionado = st.selectbox("Selecciona tu destino de la lista", opciones)

        # Filtrar por destino seleccionado
        df_filtrado = df_filtrado[df_filtrado["Destino"] == destino_seleccionado]

        # Consulta avanzada por fecha
        fechas = sorted(df_filtrado["Fecha"].dropna().unique())
        fecha_seleccionada = st.selectbox("Selecciona una fecha", fechas)

        df_filtrado_fecha = df_filtrado[df_filtrado["Fecha"] == fecha_seleccionada]

        st.markdown(f"### Resultados para destino: **{destino_seleccionado}** - fecha: **{fecha_seleccionada}**")
        st.dataframe(df_filtrado_fecha.reset_index(drop=True))

        # Botón descargar CSV
        csv_data = df_filtrado_fecha.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Descargar reporte CSV", data=csv_data, file_name=f"reporte_{destino_seleccionado}_{fecha_seleccionada}.csv")

        # Gráfica historial de estatus apilado
        fig, ax = plt.subplots(figsize=(10, 5))
        df_dest = df_filtrado.groupby(["Fecha", "Estado de atención"]).size().unstack(fill_value=0)
        df_dest.plot(kind="bar", stacked=True, ax=ax, colormap='tab20')
        ax.set_title(f"Histórico estatus pedidos para {destino_seleccionado}")
        ax.set_xlabel("Fecha")
        ax.set_ylabel("Cantidad")
        plt.xticks(rotation=45)
        plt.tight_layout()
        st.pyplot(fig)

        # Suscripción OneSignal con control de botones y estado
        suscripcion_usuario(destino_seleccionado)

    else:
        st.info("Escribe al menos 3 caracteres para buscar tu destino.")

# --- Login simple admin ---
def login_panel():
    st.sidebar.title("🔐 Admin Login")
    if "admin_logged" not in st.session_state:
        st.session_state.admin_logged = False
    if not st.session_state.admin_logged:
        user = st.sidebar.text_input("Usuario", key="user_login")
        password = st.sidebar.text_input("Contraseña", type="password", key="pass_login")
        if st.sidebar.button("Entrar"):
            if user == ADMIN_USER and password == ADMIN_PASS:
                st.session_state.admin_logged = True
                st.sidebar.success("✔️ Acceso concedido")
                st.experimental_rerun()
            else:
                st.sidebar.error("❌ Credenciales incorrectas")
    else:
        if st.sidebar.button("Cerrar sesión"):
            st.session_state.admin_logged = False
            st.experimental_rerun()

# --- Main ---
def main():
    st.title("📦 Sistema de Seguimiento de Pedidos")
    login_panel()

    if "admin_logged" in st.session_state and st.session_state.admin_logged:
        admin_panel()
    else:
        user_panel()

if __name__ == "__main__":
    main()
