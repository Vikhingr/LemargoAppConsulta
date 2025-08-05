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
        
        # --- LÍNEAS DE DIAGNÓSTICO ---
        st.info(f"Diagnóstico - Filas en archivo antiguo: {len(old_df_clean)}")
        st.info(f"Diagnóstico - Filas en archivo nuevo: {len(new_df_clean)}")
        # --- FIN LÍNEAS DE DIAGNÓSTICO ---

        key_columns = ['Destino', 'Fecha', 'Producto']
        
        # Realizar la fusión para encontrar los cambios de estado
        merged_df = pd.merge(
            old_df_clean,
            new_df_clean,
            on=key_columns,
            how='inner',
            suffixes=('_old', '_new')
        )
        
        # Filtrar solo los registros donde el estado ha cambiado
        cambios_df = merged_df[merged_df['Estado de atención_old'] != merged_df['Estado de atención_new']]
        
        # Asegurarse de que no haya duplicados en los cambios detectados
        cambios_df = cambios_df.drop_duplicates(subset=key_columns, keep='last')
        
        # AÑADIDO: Mostrar los cambios detectados en la interfaz para confirmación
        if not cambios_df.empty:
            st.header("🔍 Cambios de estatus detectados")
            st.info(f"Se detectaron {len(cambios_df)} cambios de estatus. Aquí está la tabla de cambios:")
            st.dataframe(cambios_df[['Destino', 'Fecha', 'Producto', 'Estado de atención_old', 'Estado de atención_new']])

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
