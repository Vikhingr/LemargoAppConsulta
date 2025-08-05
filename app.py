import streamlit as st
import pandas as pd
import os
from datetime import datetime
import requests
from dotenv import load_dotenv

# Cargar variables desde .env o .streamlit/secrets.toml en producción
load_dotenv()
ONESIGNAL_APP_ID = os.getenv("ONESIGNAL_APP_ID", st.secrets.get("ONESIGNAL_APP_ID"))
ONESIGNAL_API_KEY = os.getenv("ONESIGNAL_REST_API_KEY", st.secrets.get("ONESIGNAL_REST_API_KEY"))

st.set_page_config(page_title="Seguimiento de Pedidos", layout="centered")

# Cargar histórico de datos
def cargar_historico():
    try:
        return pd.read_excel("historico_estatus.xlsx")
    except FileNotFoundError:
        return pd.DataFrame()

# Suscripción a notificaciones por destino
def suscribirse_destino(destino):
    js = {
        "app_id": ONESIGNAL_APP_ID,
        "tags": {
            "destino": str(destino)
        }
    }
    st.markdown(f"""
        <script>
        window.OneSignal = window.OneSignal || [];
        OneSignal.push(function() {{
            OneSignal.showNativePrompt();
            OneSignal.sendTags({js["tags"]});
            alert("✅ Te has suscrito correctamente al destino {destino}. Recibirás notificaciones de cambios.");
        }});
        </script>
    """, unsafe_allow_html=True)

# Tarjeta visual
def mostrar_tarjeta(row):
    color = "#007bff"  # Azul por defecto
    estatus = row["Estado de atención"]
    if "cancel" in estatus.lower():
        color = "#dc3545"
    elif "entregado" in estatus.lower():
        color = "#28a745"
    elif "pendiente" in estatus.lower():
        color = "#ffc107"

    st.markdown(f"""
    <div style="border-radius: 10px; padding: 15px; margin-bottom: 10px; background-color: {color}; color: white;">
        <b>Producto:</b> {row['Producto']}<br>
        <b>Turno:</b> {row['Turno']}<br>
        <b>Tonel:</b> {row['Medio']}<br>
        <b>Capacidad:</b> {row['Capacidad programada (Litros)']} L<br>
        <b>Fecha estimada:</b> {row['Fecha y hora estimada']}<br>
        <b>Fecha de facturación:</b> {row['Fecha y hora de facturación']}<br>
        <b>Estatus:</b> {row['Estado de atención']}
    </div>
    """, unsafe_allow_html=True)

# Interfaz principal
def main():
    st.title("📦 Seguimiento de Pedidos por Destino")

    historico = cargar_historico()

    destino_input = st.text_input("🔍 Ingresa el número exacto de tu destino (ej. 58):")
    if destino_input:
        if destino_input.isdigit():
            df_filtrado = historico[historico["Destino"].astype(str) == destino_input]
            if not df_filtrado.empty:
                st.markdown(f"### Resultados para destino **{destino_input}**")
                
                # Botón de suscripción
                with st.expander("🔔 Suscribirse a este destino"):
                    st.markdown("Al suscribirte, recibirás notificaciones automáticas cuando cambie el estatus de tus pedidos.")
                    if st.button("✅ Suscribirse a este destino"):
                        suscribirse_destino(destino_input)

                for _, row in df_filtrado.iterrows():
                    mostrar_tarjeta(row)
            else:
                st.warning("No se encontraron pedidos para ese destino.")
        else:
            st.warning("Por favor ingresa solo el número del destino.")

if __name__ == "__main__":
    main()
