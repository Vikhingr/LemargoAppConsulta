import streamlit as st
import pandas as pd
import os
import datetime
import requests
import io
import matplotlib.pyplot as plt

# ================================
# CARGA DE VARIABLES DE SECRETO
# ================================
ONESIGNAL_APP_ID = st.secrets["ONESIGNAL_APP_ID"]
ONESIGNAL_REST_API_KEY = st.secrets["ONESIGNAL_REST_API_KEY"]
ADMIN_USER = st.secrets["ADMIN_USER"]
ADMIN_PASS = st.secrets["ADMIN_PASS"]

# ================================
# CONFIGURACIÓN GENERAL
# ================================
st.set_page_config(page_title="Seguimiento de Pedidos", layout="wide")

# ================================
# FUNCIONES
# ================================
def enviar_notificacion_push(titulo, mensaje, segment):
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Basic {ONESIGNAL_REST_API_KEY}"
    }
    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "included_segments": ["Subscribed Users"],
        "filters": [
            {"field": "tag", "key": "destino_fecha", "relation": "=", "value": segment}
        ],
        "headings": {"en": titulo},
        "contents": {"en": mensaje}
    }
    r = requests.post("https://onesignal.com/api/v1/notifications", headers=headers, json=payload)
    return r.status_code == 200

def cargar_datos_excel(archivo):
    return pd.read_excel(archivo)

def guardar_historico(df, archivo="historico_estatus.xlsx"):
    df.to_excel(archivo, index=False)

def leer_historico(archivo="historico_estatus.xlsx"):
    if os.path.exists(archivo):
        return pd.read_excel(archivo)
    else:
        return pd.DataFrame()

def comparar_y_actualizar(historico, nuevo):
    nuevo["ID"] = nuevo["Destino"].astype(str) + "_" + pd.to_datetime(nuevo["Fecha"]).dt.strftime("%Y-%m-%d")
    historico["ID"] = historico["Destino"].astype(str) + "_" + pd.to_datetime(historico["Fecha"]).dt.strftime("%Y-%m-%d")

    df_merged = pd.merge(nuevo, historico, on="ID", how="left", suffixes=('', '_old'))
    cambios = df_merged[df_merged["Estado de atención"] != df_merged["Estado de atención_old"]]

    registros_actualizados = []
    for _, fila in cambios.iterrows():
        fila_dict = fila[nuevo.columns].to_dict()
        fila_dict["Hora consulta"] = datetime.datetime.now()
        fila_dict["Fuente"] = "actualización"
        registros_actualizados.append(fila_dict)
        enviar_notificacion_push(
            titulo=f"Pedido actualizado: {fila['Destino']}",
            mensaje=f"Nuevo estatus: {fila['Estado de atención']}",
            segment=fila["ID"]
        )

    df_actualizados = pd.DataFrame(registros_actualizados)
    historico = pd.concat([historico, df_actualizados], ignore_index=True)
    historico.drop_duplicates(subset=["ID", "Estado de atención"], keep="last", inplace=True)

    return historico

def mostrar_grafica_destino(historico, destino):
    df = historico[historico["Destino"] == destino]
    if df.empty:
        st.warning("No hay datos para este destino.")
        return
    df = df.sort_values("Fecha")
    conteo = df.groupby(["Fecha", "Estado de atención"]).size().unstack().fillna(0)
    conteo.plot(kind='bar', stacked=True)
    st.pyplot(plt.gcf())
    plt.clf()

# ================================
# PÁGINA DE ADMIN
# ================================
def pagina_admin():
    st.title("Panel de Administración")
    st.markdown("### Subir nuevo archivo de pedidos")

    archivo_cargado = st.file_uploader("Selecciona el archivo Excel", type=["xlsx"])
    if archivo_cargado and st.button("Actualizar Base"):
        nuevo_df = cargar_datos_excel(archivo_cargado)
        historico_df = leer_historico()
        actualizado_df = comparar_y_actualizar(historico_df, nuevo_df)
        guardar_historico(actualizado_df)
        st.success("Base actualizada correctamente.")

    st.markdown("---")
    st.markdown("### Ver histórico completo")
    df = leer_historico()
    st.dataframe(df)

# ================================
# PÁGINA DE USUARIO
# ================================
def pagina_usuario():
    st.title("Consulta de Pedido")

    destino = st.text_input("Ingresa tu número de destino")
    fecha = st.date_input("Selecciona la fecha del pedido")

    if destino and fecha:
        df = leer_historico()
        df = df[df["Destino"] == destino]
        df = df[pd.to_datetime(df["Fecha"]).dt.date == fecha]

        if df.empty:
            st.warning("No se encontró información.")
        else:
            st.success("Resultado encontrado:")
            st.dataframe(df[[
                "Fecha", "Folio Pedido", "Destino", "Producto",
                "Presentación", "Transportista", "Estado de atención"
            ]])

            # Suscripción personalizada
            st.markdown(f"""
            <script src="https://cdn.onesignal.com/sdks/OneSignalSDK.js" async=""></script>
            <script>
              window.OneSignal = window.OneSignal || [];
              OneSignal.push(function() {{
                OneSignal.init({{
                  appId: "{ONESIGNAL_APP_ID}",
                  notifyButton: {{
                    enable: true,
                  }},
                  allowLocalhostAsSecureOrigin: true
                }});
                OneSignal.sendTag("destino_fecha", "{destino}_{fecha}");
              }});
            </script>
            """, unsafe_allow_html=True)

            # Historial visual
            st.markdown("### Historial visual del destino")
            mostrar_grafica_destino(leer_historico(), destino)

            # Botón exportar
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False)
            st.download_button("📤 Descargar reporte", buffer.getvalue(), file_name=f"reporte_{destino}_{fecha}.xlsx")

# ================================
# MENÚ PRINCIPAL
# ================================
def main():
    menu = st.sidebar.selectbox("Menú", ["Usuario", "Admin"])

    if menu == "Admin":
        usuario = st.text_input("Usuario")
        contraseña = st.text_input("Contraseña", type="password")
        if usuario == ADMIN_USER and contraseña == ADMIN_PASS:
            pagina_admin()
        else:
            st.warning("Credenciales incorrectas.")
    else:
        pagina_usuario()

if __name__ == "__main__":
    main()
