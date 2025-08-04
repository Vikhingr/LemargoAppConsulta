import streamlit as st
import pandas as pd
import os
import datetime
import requests
import matplotlib.pyplot as plt

# --- Carga secretos ---
ONESIGNAL_APP_ID = st.secrets["ONESIGNAL_APP_ID"]
ONESIGNAL_REST_API_KEY = st.secrets["ONESIGNAL_REST_API_KEY"]
ADMIN_USER = st.secrets["ADMIN_USER"]
ADMIN_PASS = st.secrets["ADMIN_PASS"]

# --- Configuración visual dark ---
st.set_page_config(page_title="Seguimiento de Pedidos", layout="wide")
st.markdown("""
    <style>
    body, .stApp {
        background-color: #121212;
        color: #e0e0e0;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        background-color: #1f2937;
        color: white;
        border-radius: 6px;
        padding: 6px;
    }
    .stButton>button {
        background-color: #3b82f6;
        color: white;
        border-radius: 8px;
        font-weight: 600;
        padding: 8px 16px;
        border: none;
        transition: background-color 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #2563eb;
        cursor: pointer;
    }
    .stAlert {
        background-color: #333;
        color: #ddd;
        border-radius: 6px;
    }
    footer {
        visibility: hidden;
    }
    </style>
""", unsafe_allow_html=True)

# --- Función para enviar notificación (usado en admin) ---
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
        st.success("✅ Notificación enviada")
    except Exception as e:
        st.error(f"❌ Error enviando notificación: {e}")

# --- Consolida datos y detecta cambios ---
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

# --- Sesión admin ---
if "admin_logged" not in st.session_state:
    st.session_state.admin_logged = False

def login_panel():
    col1, col2 = st.columns([1,3])
    with col1:
        st.markdown("### 🔐 Admin Login")
        user = st.text_input("Usuario", key="user_login")
        password = st.text_input("Contraseña", type="password", key="pass_login")
        if st.button("Entrar"):
            if user == ADMIN_USER and password == ADMIN_PASS:
                st.session_state.admin_logged = True
                st.experimental_rerun()
            else:
                st.error("❌ Credenciales incorrectas")
    return col2

def admin_section(col):
    with col:
        st.markdown("### 📤 Subir archivo nuevo_datos.xlsx")
        archivo = st.file_uploader("Selecciona archivo (.xlsx)", type=["xlsx"])
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

# --- Sección usuario ---
def user_section():
    st.markdown("## 🔎 Consulta de Pedido")
    if not os.path.exists("historico_estatus.xlsx"):
        st.warning("Aún no hay datos disponibles. Espera a que el administrador cargue la base.")
        return

    df_hist = pd.read_excel("historico_estatus.xlsx")
    destinos = sorted(df_hist["Destino"].unique())

    # Buscador exacto (sin dropdown múltiple)
    destino_input = st.text_input("Ingresa tu número de destino exacto")

    if destino_input:
        if destino_input not in destinos:
            st.error("Destino no encontrado. Verifica el número ingresado.")
            return

        df_destino = df_hist[df_hist["Destino"] == destino_input]

        # Consulta avanzada por fecha
        fechas = sorted(df_destino["Fecha"].unique())
        fecha_sel = st.selectbox("Selecciona una fecha", fechas)
        df_filtrado = df_destino[df_destino["Fecha"] == fecha_sel]

        st.dataframe(df_filtrado.style.set_properties(**{"text-align": "center"}))

        # Botón exportar CSV
        csv_data = df_filtrado.to_csv(index=False).encode()
        st.download_button("📥 Descargar reporte CSV", data=csv_data, file_name=f"reporte_{destino_input}_{fecha_sel}.csv")

        # Gráfica historial estatus
        fig, ax = plt.subplots(figsize=(8,4))
        df_destino.groupby("Fecha")["Estado de atención"].value_counts().unstack().fillna(0).plot(
            kind="bar", stacked=True, ax=ax, colormap='tab20'
        )
        ax.set_title("Historial de estatus por fecha")
        ax.set_ylabel("Cantidad")
        ax.set_xlabel("Fecha")
        plt.xticks(rotation=45)
        plt.tight_layout()
        st.pyplot(fig)

        # Explicación suscripción
        st.markdown("""
            <div style="background-color:#1f2937; padding:15px; border-radius:8px; margin-top:15px;">
                <b>Suscripción a notificaciones:</b><br>
                Puedes suscribirte para recibir notificaciones automáticas cada vez que cambie el estatus de tu pedido para este destino.<br>
                Al suscribirte, se te pedirá permiso para enviar notificaciones.<br>
                Puedes cancelar la suscripción en cualquier momento con el botón que aparece abajo.
            </div>
        """, unsafe_allow_html=True)

        # Botones suscribir / cancelar suscripción con JS + OneSignal
        st.markdown(f"""
            <script src="https://cdn.onesignal.com/sdks/OneSignalSDK.js" async=""></script>
            <script>
                window.OneSignal = window.OneSignal || [];
                OneSignal.push(function() {{
                    OneSignal.init({{
                        appId: "{ONESIGNAL_APP_ID}",
                    }});
                }});

                function updateSubscriptionStatus() {{
                    OneSignal.isPushNotificationsEnabled(function(isEnabled) {{
                        const btnSubscribe = document.getElementById('btnSubscribe');
                        const btnUnsubscribe = document.getElementById('btnUnsubscribe');
                        const statusMsg = document.getElementById('statusMsg');
                        if (isEnabled) {{
                            btnSubscribe.style.display = 'none';
                            btnUnsubscribe.style.display = 'inline-block';
                            statusMsg.textContent = '📲 Estás suscrito a las notificaciones para destino: {destino_input}';
                        }} else {{
                            btnSubscribe.style.display = 'inline-block';
                            btnUnsubscribe.style.display = 'none';
                            statusMsg.textContent = '❌ No estás suscrito a notificaciones para este destino.';
                        }}
                    }});
                }}

                function subscribe() {{
                    OneSignal.push(function() {{
                        OneSignal.showSlidedownPrompt().then(function() {{
                            OneSignal.sendTag("destino", "{destino_input}").then(function() {{
                                updateSubscriptionStatus();
                            }});
                        }});
                    }});
                }}

                function unsubscribe() {{
                    OneSignal.push(function() {{
                        OneSignal.deleteTag("destino").then(function() {{
                            updateSubscriptionStatus();
                        }});
                    }});
                }}

                document.addEventListener("DOMContentLoaded", function() {{
                    updateSubscriptionStatus();
                }});
            </script>

            <div style="margin-top:10px;">
                <button id="btnSubscribe" onclick="subscribe()" style="background:#2563eb; color:white; border:none; border-radius:6px; padding:8px 16px; font-weight:bold; cursor:pointer;">
                    🔔 Suscribirse a notificaciones
                </button>
                <button id="btnUnsubscribe" onclick="unsubscribe()" style="background:#ef4444; color:white; border:none; border-radius:6px; padding:8px 16px; font-weight:bold; cursor:pointer; display:none;">
                    🔕 Cancelar suscripción
                </button>
                <p id="statusMsg" style="margin-top:8px; font-weight:bold;"></p>
            </div>
        """, unsafe_allow_html=True)

# --- MAIN ---
def main():
    st.title("📦 Seguimiento de Pedidos")

    if "admin_logged" not in st.session_state:
        st.session_state.admin_logged = False

    if st.session_state.admin_logged:
        col = login_panel()
        admin_section(col)
    else:
        login_panel()
        user_section()

if __name__ == "__main__":
    main()
