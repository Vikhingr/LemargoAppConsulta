import streamlit as st
import pandas as pd
import os
import datetime
import requests
import matplotlib.pyplot as plt

# Cargar secretos
ONESIGNAL_APP_ID = st.secrets["ONESIGNAL_APP_ID"]
ONESIGNAL_REST_API_KEY = st.secrets["ONESIGNAL_REST_API_KEY"]
ADMIN_USER = st.secrets["ADMIN_USER"]
ADMIN_PASS = st.secrets["ADMIN_PASS"]

# Configuración visual
st.set_page_config(page_title="Seguimiento de Pedidos", layout="wide")
st.markdown("""
    <style>
    body {
        background-color: #111827;
        color: #e5e7eb;
    }
    .stApp {
        background-color: #111827;
    }
    .stTextInput>div>div>input {
        background-color: #1f2937;
        color: white;
    }
    .stSelectbox>div>div>div {
        background-color: #1f2937;
        color: white;
    }
    .stButton>button {
        background-color: #2563eb;
        color: white;
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# Función para enviar notificaciones
def enviar_notificacion(destino, mensaje):
    url = "https://onesignal.com/api/v1/notifications"
    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "included_segments": ["Subscribed Users"],
        "filters": [{"field": "tag", "key": "destino", "relation": "=", "value": destino}],
        "contents": {"en": mensaje}
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {ONESIGNAL_REST_API_KEY}"
    }
    requests.post(url, json=payload, headers=headers)

# Consolidación de datos
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

    df_final.to_excel("historico_estatus.xlsx", index=False)

    for destino, viejo, nuevo in cambios:
        mensaje = f"Tu pedido cambió de '{viejo}' a '{nuevo}'"
        enviar_notificacion(destino, mensaje)

# Sesión de login
if "admin_logged" not in st.session_state:
    st.session_state.admin_logged = False

col1, col2 = st.columns([1, 3])

with col1:
    st.markdown("## Admin Login")
    user = st.text_input("Usuario", key="user_login")
    password = st.text_input("Contraseña", type="password", key="pass_login")
    if st.button("Entrar"):
        if user == ADMIN_USER and password == ADMIN_PASS:
            st.session_state.admin_logged = True
            st.success("Acceso concedido")
        else:
            st.error("Credenciales incorrectas")

# Sección Admin
if st.session_state.admin_logged:
    with col2:
        st.markdown("## Sección Administrador")
        archivo = st.file_uploader("Subir archivo nuevo_datos.xlsx", type=["xlsx"])
        if archivo:
            with open("nuevo_datos.xlsx", "wb") as f:
                f.write(archivo.getbuffer())
            st.success("Archivo cargado correctamente")

        if st.button("Actualizar Base"):
            try:
                df_nuevo = pd.read_excel("nuevo_datos.xlsx")
                actualizar_base(df_nuevo)
                st.success("Base actualizada y cambios notificados")
            except Exception as e:
                st.error(f"Error al actualizar: {str(e)}")

# Sección Usuario
else:
    st.markdown("## Consulta de Pedido")
    try:
        df_hist = pd.read_excel("historico_estatus.xlsx")
        destinos = sorted(df_hist["Destino"].unique())
        destino_sel = st.selectbox("Selecciona tu destino", destinos)
        df_destino = df_hist[df_hist["Destino"] == destino_sel]

        # Consulta avanzada
        fechas = sorted(df_destino["Fecha"].unique())
        fecha_sel = st.selectbox("Selecciona una fecha", fechas)
        df_filtrado = df_destino[df_destino["Fecha"] == fecha_sel]

        st.dataframe(df_filtrado)

        # Exportar
        st.download_button("Descargar reporte", data=df_filtrado.to_csv(index=False).encode(), file_name=f"reporte_{destino_sel}.csv")

        # Historial visual
        fig, ax = plt.subplots()
        df_destino.groupby("Fecha")["Estado de atención"].value_counts().unstack().fillna(0).plot(kind="bar", stacked=True, ax=ax)
        ax.set_title("Historial de estatus por fecha")
        ax.set_ylabel("Cantidad")
        st.pyplot(fig)

        # Script OneSignal para suscripción por destino
        st.markdown(f"""
        <script src="https://cdn.onesignal.com/sdks/OneSignalSDK.js" async=""></script>
        <script>
            window.OneSignal = window.OneSignal || [];
            OneSignal.push(function() {{
                OneSignal.init({{
                    appId: "{ONESIGNAL_APP_ID}",
                }});
                OneSignal.sendTag("destino", "{destino_sel}");
            }});
        </script>
        """, unsafe_allow_html=True)

    except FileNotFoundError:
        st.warning("Aún no hay datos disponibles. Espera a que el administrador cargue la base.")
