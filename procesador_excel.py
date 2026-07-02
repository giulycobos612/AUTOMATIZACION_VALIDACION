import asyncio
import os
import sys
import pandas as pd

# Añadir el directorio actual al path para que encuentre la carpeta 'src'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.validator import PublicationValidator

async def main():
    print("\n" + "="*70)
    print("PROCESADOR MASIVO DE DOI/ISSN (EXCEL)")
    print("="*70 + "\n")
    
    if not os.environ.get("GROQ_API_KEY"):
        print("ADVERTENCIA: No se ha detectado la variable GROQ_API_KEY.")
        print("Por favor, pega tu llave de Groq aqui: ", end="")
        key = input().strip()
        if not key:
            print("Error: Se requiere una llave de Groq (gsk_...) para continuar.")
            return
        os.environ["GROQ_API_KEY"] = key

    archivo_entrada = "registros_entrada.xlsx"
    archivo_salida = "resultados_validacion.xlsx"

    if not os.path.exists(archivo_entrada):
        print(f"ERROR: No se encontro el archivo '{archivo_entrada}'.")
        print("Por favor, coloca tu archivo Excel en esta carpeta y ejecutame de nuevo.")
        return
        
    print(f"Leyendo '{archivo_entrada}'...")
    try:
        df = pd.read_excel(archivo_entrada)
    except Exception as e:
        print(f"Error al leer el archivo Excel: {e}")
        return
        
    if df.empty:
        print("El archivo Excel esta vacio.")
        return
        
    # Verificar columnas requeridas
    columnas_esperadas = ["TIPO", "CODIGO", "TITULO", "AUTORES_EDITORIAL"]
    for col in columnas_esperadas:
        if col not in df.columns:
            print(f"ADVERTENCIA: No se encontro la columna '{col}'. El archivo debe tener columnas: TIPO, CODIGO, TITULO, AUTORES_EDITORIAL.")
            print("Asegurate de generar la plantilla o usar esos nombres exactos de columna.")
            return

    print(f"Se encontraron {len(df)} registros. Preparando lote...")
    
    registros_a_procesar = []
    
    for idx, row in df.iterrows():
        tipo = str(row["TIPO"]).strip().upper()
        codigo = str(row["CODIGO"]).strip()
        titulo = str(row["TITULO"]).strip() if pd.notna(row["TITULO"]) else ""
        autores = str(row["AUTORES_EDITORIAL"]).strip() if pd.notna(row["AUTORES_EDITORIAL"]) else ""
        
        # Validar tipo basico
        if tipo not in ["DOI", "ISSN"]:
            tipo = "DOI" if "10." in codigo else "ISSN"
            
        registro = {
            "id_registro": f"Fila_{idx+2}", # +2 porque la fila 1 es el header y el index empieza en 0
            "tipo_publicacion": "ARTICULO" if tipo == "DOI" else "REVISTA",
            "titulo": titulo if titulo else "Desconocido",
            "autores": autores if autores else "Desconocidos",
            "anio_publicacion": "",
            "revista_editorial": autores if tipo == "ISSN" else ""
        }
        
        if tipo == "DOI":
            registro["codigo_doi"] = codigo
            registro["codigo_issn"] = ""
        else:
            registro["codigo_doi"] = ""
            registro["codigo_issn"] = codigo
            
        registros_a_procesar.append(registro)
        
    validador = PublicationValidator()
    
    print("\nProcesando lote en paralelo con Inteligencia Artificial... (Esto tomará aproximadamente unos segundos)")
    
    from tqdm.asyncio import tqdm_asyncio
    
    # Usamos el validador pero con tqdm para ver el progreso real
    ai_sem = asyncio.Semaphore(1)
    
    async def process_with_progress(rec):
        return await validador.validate_record(rec, ai_semaphore=ai_sem)
        
    tasks = [process_with_progress(rec) for rec in registros_a_procesar]
    
    # gather ejecuta todo y respeta el orden original, además tqdm_asyncio muestra barra!
    resultados_list = await tqdm_asyncio.gather(*tasks, desc="Validando", unit="reg")
    
    # Cerrar la sesión de red limpia
    if hasattr(validador.fetcher, 'close'):
        await validador.fetcher.close()
    
    print("\nCreando archivo de resultados auto-formateado...")
    
    coincide_list = [res.coincide for res in resultados_list]
    observaciones_list = [res.observaciones for res in resultados_list]
    datos_oficiales_list = [res.publicacion_encontrada for res in resultados_list]
        
    df["COINCIDE_IA"] = coincide_list
    df["OBSERVACIONES_IA"] = observaciones_list
    df["DATOS_OFICIALES"] = datos_oficiales_list
    
    try:
        # Guardar con formato usando xlsxwriter
        writer = pd.ExcelWriter(archivo_salida, engine='xlsxwriter')
        df.to_excel(writer, index=False, sheet_name='Resultados')
        
        workbook = writer.book
        worksheet = writer.sheets['Resultados']
        
        # Auto-ajustar columnas
        formato_celda = workbook.add_format({'text_wrap': True, 'valign': 'top'})
        for idx, col in enumerate(df.columns):
            max_len = max(
                df[col].astype(str).map(len).max(),
                len(col)
            ) + 2
            # Limitar ancho máximo a 50 para que no sea inmensamente ancho
            max_len = min(max_len, 50)
            worksheet.set_column(idx, idx, max_len, formato_celda)
            
        writer.close()
        
        print("="*70)
        print(f"¡EXITO! Los resultados se han guardado en '{archivo_salida}'.")
        print("="*70)
    except Exception as e:
        print(f"Error al guardar el archivo: {e}")
        print("Asegurate de que el archivo no este abierto en Excel.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProceso cancelado.")
