import streamlit as st
import pandas as pd
import asyncio
import io
import os
import sys

# Añadir ruta al sys.path para importar módulos locales
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.validator import PublicationValidator

st.set_page_config(page_title="Validador DOI/ISSN Matemático", page_icon="📚", layout="centered")

st.title("Validador de DOI e ISSN (Similitud Matemática)")
st.markdown("Sube tu archivo Excel con registros bibliográficos. El sistema conectará con Crossref/OpenAlex y aplicará un motor matemático para validar si el título coincide con el código oficial.")

# Ya no se pide API KEY de Groq

# Subir Archivo Excel
uploaded_file = st.file_uploader("📂 Sube tu archivo Excel", type=["xlsx"])

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        
        columnas_esperadas = ["TIPO", "CODIGO", "TITULO"]
        faltantes = [col for col in columnas_esperadas if col not in df.columns]
        
        if faltantes:
            st.error(f"❌ Faltan las siguientes columnas en tu Excel: {', '.join(faltantes)}")
            st.info("Asegúrate de que el archivo tenga exactamente estas columnas: TIPO, CODIGO, TITULO.")
            st.stop()
            
        st.success(f"✅ Archivo cargado correctamente. Se encontraron {len(df)} registros.")
        
        if st.button("🚀 Iniciar Validación Rápida", type="primary"):
            
            async def ejecutar_validacion():
                registros_a_procesar = []
                for idx, row in df.iterrows():
                    tipo = str(row.get("TIPO", "")).strip().upper()
                    codigo = str(row.get("CODIGO", "")).strip()
                    titulo = str(row.get("TITULO", "")).strip() if pd.notna(row.get("TITULO", "")) else ""
                    
                    if tipo not in ["DOI", "ISSN"]:
                        tipo = "DOI" if "10." in codigo else "ISSN"
                        
                    registro = {
                        "id_registro": f"Fila_{idx+2}",
                        "tipo_publicacion": "ARTICULO" if tipo == "DOI" else "REVISTA",
                        "titulo": titulo if titulo else "Desconocido",
                        "autores": "",
                        "anio_publicacion": "",
                        "revista_editorial": ""
                    }
                    
                    if tipo == "DOI":
                        registro["codigo_doi"] = codigo
                        registro["codigo_issn"] = ""
                    else:
                        registro["codigo_doi"] = ""
                        registro["codigo_issn"] = codigo
                        
                    registros_a_procesar.append(registro)
                    
                validador = PublicationValidator(threshold=0.85)
                
                status_text = st.empty()
                status_text.info("Procesando lote con motor matemático de alta velocidad...")
                
                # Ejecutar de forma concurrente veloz
                report = await validador.validate_batch(registros_a_procesar)
                return report.resultados

            with st.spinner('⚡ Consultando APIs oficiales y calculando similitud...'):
                resultados_list = asyncio.run(ejecutar_validacion())
                
            st.success("✅ ¡Validación completada con éxito!")
            
            # Preparar el DataFrame de salida
            df_out = df.copy()
            df_out["%_SIMILITUD"] = [res.similitud for res in resultados_list]
            df_out["COINCIDE_MATH"] = [res.coincide for res in resultados_list]
            df_out["OBSERVACIONES"] = [res.observaciones for res in resultados_list]
            df_out["TITULO_OFICIAL"] = [res.publicacion_encontrada for res in resultados_list]
            
            # Guardar en memoria (BytesIO) para el botón de descarga
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_out.to_excel(writer, index=False, sheet_name='Resultados')
                workbook = writer.book
                worksheet = writer.sheets['Resultados']
                
                formato_celda = workbook.add_format({'text_wrap': True, 'valign': 'top'})
                for idx, col in enumerate(df_out.columns):
                    max_len = max(df_out[col].astype(str).map(len).max(), len(col)) + 2
                    max_len = min(max_len, 50) # Limitar ancho a 50
                    worksheet.set_column(idx, idx, max_len, formato_celda)
            
            excel_data = output.getvalue()
            
            st.balloons()
            st.download_button(
                label="📥 Descargar Reporte de Resultados (Excel)",
                data=excel_data,
                file_name="resultados_validacion_matematica.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
            
            # Mostrar vista previa en la web
            st.write("👀 Vista previa de los resultados:")
            st.dataframe(df_out)
            
    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {e}")
