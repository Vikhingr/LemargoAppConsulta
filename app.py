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

# Configuración visual dark moderna
st.set_page_config(page_title="Seguimiento de Pedidos", layout="wide")
st.markdown("""
    <style>
    body, .stApp {
        background-color: #121212;
        color: #e0e0e0;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        background-color: #1e1e1e;
        color: #e0e0e0;
        border-radius: 6px;
        padding: 6px 10px;
        border: 1px solid #444;
    }
    .stButton>button {
        background-color: #4f46e5;
        color: white;
        font-weight: 600;
        border-radius: 8px;
        padding: 8px 20px;
        transition: background-color 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #3730a3;
    }
    .sidebar .sidebar-content {
        background-color: #1f2937;
        color: #cbd5e1;
    }
    .css-1d391kg {  /* área de alertas, info, warning */
        background-color: #1e293b !important;
        border-radius: 8px;
        padding: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# Función para enviar notificaciones OneSignal por destino
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
    except Exception as e:
        st.error(f"Error al enviar notificación: {e}")

# Actualiza y consolida base, detecta cambios y notifica
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
            cambios.append((fila["Destino"], None, nuevo_estatus))

    df_final.to_excel("historico_estatus.xlsx", index=False)

    for destino, viejo, nuevo in cambios:
        if viejo is None:
            mensaje = f"Nuevo pedido registrado con estatus '{nuevo}'."
        else:
            mensaje = f"Tu pedido cambió de '{viejo}' a '{nuevo}'."
        enviar_notificacion(destino, mensaje)

# Panel login (sin retorno, para evitar error rerun)
def login_panel():
    st.markdown("### 🔐 Admin Login")
    user = st.text_input("Usuario", key="user_login")
    password = st.text_input("Contraseña", type="password", key="pass_login")
    if st.button("Entrar"):
        if user == ADMIN_USER and password == ADMIN_PASS:
            st.session_state.admin_logged = True
            st.success("Acceso concedido")
            st.experimental_rerun()
        else:
            st.error("❌ Credenciales incorrectas")

# Panel admin con carga y actualización base
def admin_section():
    st.markdown("### 📤 Sección Administrador")
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

# Sección usuario con búsqueda y suscripción
def user_section():
    st.markdown("## Consulta de Pedido")

    if not os.path.exists("historico_estatus.xlsx"):
        st.warning("Aún no hay datos disponibles. Espera a que el administrador cargue la base.")
        return

    df_hist = pd.read_excel("historico_estatus.xlsx")
    destinos = sorted(df_hist["Destino"].unique())

    destino_input = st.text_input("Escribe tu número de destino exacto para buscar")

    destino_sel = None
    if destino_input:
        # búsqueda exacta ignorando espacios
        destino_input = destino_input.strip()
        if destino_input in destinos:
            destino_sel = destino_input
        else:
            st.warning("Destino no encontrado. Asegúrate de ingresar el número exacto.")

    if destino_sel:
        st.success(f"Destino seleccionado: {destino_sel}")

        # Confirmación de suscripción
        st.markdown("""
            <p style="font-size: 14px; color: #cbd5e1;">
            Puedes suscribirte para recibir notificaciones cuando cambie el estatus de tu pedido.
            </p>
        """, unsafe_allow_html=True)

        if st.button("Suscribirme a notificaciones para este destino"):
            st.markdown(f"""
                <script src="https://cdn.onesignal.com/sdks/OneSignalSDK.js" async=""></script>
                <script>
                    window.OneSignal = window.OneSignal || [];
                    OneSignal.push(function() {{
                        OneSignal.init({{
                            appId: "{ONESIGNAL_APP_ID}",
                        }});
                        OneSignal.sendTag("destino", "{destino_sel}");
                        alert("¡Suscripción realizada para destino {destino_sel}!");
                    }});
                </script>
            """, unsafe_allow_html=True)

        df_filtrado = df_hist[df_hist["Destino"] == destino_sel]
        df_filtrado = df_filtrado.sort_values("Fecha", ascending=False).reset_index(drop=True)

        st.dataframe(df_filtrado)

        st.download_button(
            label="📥 Descargar reporte CSV",
            data=df_filtrado.to_csv(index=False).encode(),
            file_name=f"reporte_{destino_sel}.csv",
            mime="text/csv"
        )

        # Historial visual con matplotlib
        fig, ax = plt.subplots(figsize=(8, 4))
        try:
            df_plot = df_filtrado.groupby("Fecha")["Estado de atención"].value_counts().unstack().fillna(0)
            df_plot.plot(kind="bar", stacked=True, ax=ax, colormap="viridis")
            ax.set_title(f"Historial de estatus para destino {destino_sel}")
            ax.set_xlabel("Fecha")
            ax.set_ylabel("Cantidad")
            ax.legend(title="Estado")
            st.pyplot(fig)
        except Exception as e:
            st.warning(f"No se pudo generar gráfico: {e}")

def main():
    st.title("📦 Seguimiento de Pedidos")

    if "admin_logged" not in st.session_state:
        st.session_state.admin_logged = False

    # Sidebar para cerrar sesión admin
    if st.session_state.admin_logged:
        if st.sidebar.button("🔒 Cerrar sesión Admin"):
            st.session_state.admin_logged = False
            st.experimental_rerun()

    # Mostrar panel admin o login o usuario según estado
    if st.session_state.admin_logged:
        admin_section()
    else:
        login_panel()
        user_section()

if __name__ == "__main__":
    main()
