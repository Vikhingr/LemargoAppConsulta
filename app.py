import streamlit as st
import pandas as pd
import os
import datetime
import requests

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
    .card {
        background-color: #1f2937;
        padding: 15px;
        border-radius: 12px;
        margin-bottom: 10px;
        border: 1px solid #374151;
    }
    .card p {
        margin: 0;
        font-size: 14px;
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

# Login centrado, moderno
def login_panel():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## 🔐 Iniciar sesión como administrador")
        user = st.text_input("Usuario", key="user_login")
        password = st.text_input("Contraseña", type="password", key="pass_login")
        if st.button("Entrar"):
            if user == ADMIN_USER and password == ADMIN_PASS:
                st.session_state.admin_logged = True
                st.success("✅ Acceso concedido")
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

# Sección usuario con búsqueda y tarjetas
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
        destino_input = destino_input.strip()
        if destino_input in destinos:
            destino_sel = destino_input
        else:
            st.warning("Destino no encontrado. Asegúrate de ingresar el número exacto.")

    if destino_sel:
        st.success(f"Destino seleccionado: {destino_sel}")

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

        columnas_mostrar = [
            "Producto", "Turno", "Tonel", "Capacidad programada (Litros)",
            "Fecha y hora estimada", "Fecha y hora de facturación", "Estado de atención"
        ]
        df_filtrado = df_hist[df_hist["Destino"] == destino_sel]
        df_filtrado = df_filtrado[columnas_mostrar].sort_values("Fecha y hora estimada", ascending=False)

        for _, row in df_filtrado.iterrows():
            st.markdown(f"""
                <div class="card">
                    <p><strong>Producto:</strong> {row['Producto']}</p>
                    <p><strong>Turno:</strong> {row['Turno']}</p>
                    <p><strong>Tonel:</strong> {row['Tonel']}</p>
                    <p><strong>Capacidad:</strong> {row['Capacidad programada (Litros)']} L</p>
                    <p><strong>Fecha estimada:</strong> {row['Fecha y hora estimada']}</p>
                    <p><strong>Facturación:</strong> {row['Fecha y hora de facturación']}</p>
                    <p><strong>Estado:</strong> {row['Estado de atención']}</p>
                </div>
            """, unsafe_allow_html=True)

# Función principal
def main():
    st.title("📦 Seguimiento de Pedidos")

    if "admin_logged" not in st.session_state:
        st.session_state.admin_logged = False

    if st.session_state.admin_logged:
        if st.sidebar.button("🔒 Cerrar sesión Admin"):
            st.session_state.admin_logged = False
            st.experimental_rerun()

    if st.session_state.admin_logged:
        admin_section()
    else:
        login_panel()
        st.stop()
        user_section()

if __name__ == "__main__":
    main()
