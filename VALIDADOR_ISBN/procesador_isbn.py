import asyncio
import os
import sys
import pandas as pd
from tqdm.asyncio import tqdm

# Añadir el directorio actual al path para que encuentre la carpeta 'src'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.validator import BookValidator
from src.models import BookRecord

async def main():
    print("\n" + "="*70)
    print("PROCESADOR MASIVO DE ISBN PARA LIBROS")
    print("="*70 + "\n")
    
    if not os.environ.get("GROQ_API_KEY"):
        print("ADVERTENCIA: No se ha detectado la variable GROQ_API_KEY.")
        key = input("Por favor, pega tu llave de Groq aqui: ").strip()
        if not key:
            print("Error: Se requiere una llave de Groq (gsk_...) para continuar.")
            return
        os.environ["GROQ_API_KEY"] = key

    archivo_entrada = "registros_libros.xlsx"
    archivo_salida = "resultados_validacion_libros.xlsx"

    if not os.path.exists(archivo_entrada):
        print(f"ERROR: No se encontró el archivo '{archivo_entrada}'.")
        print("Por favor, crea un archivo Excel con ese nombre con las columnas requeridas y ejecuta de nuevo.")
        return
        
    print(f"Leyendo '{archivo_entrada}'...")
    try:
        df = pd.read_excel(archivo_entrada)
    except Exception as e:
        print(f"Error al leer el archivo Excel: {e}")
        return
        
    if df.empty:
        print("El archivo Excel está vacío.")
        return
        
    # Verificar columnas requeridas
    columnas_esperadas = ["ISBN", "TITULO", "AUTORES", "EDITORIAL", "ANIO_PUBLICACION"]
    for col in columnas_esperadas:
        if col not in df.columns:
            print(f"ERROR: Falta la columna obligatoria '{col}' en el Excel.")
            return

    # Convertir el DataFrame a una lista de BookRecord
    records_to_validate = []
    
    for idx, row in df.iterrows():
        isbn_raw = str(row["ISBN"]).strip() if pd.notna(row.get("ISBN")) else ""
        titulo = str(row["TITULO"]).strip() if pd.notna(row.get("TITULO")) else ""
        autores = str(row["AUTORES"]).strip() if pd.notna(row.get("AUTORES")) else ""
        editorial = str(row["EDITORIAL"]).strip() if pd.notna(row.get("EDITORIAL")) else ""
        anio = str(row["ANIO_PUBLICACION"]).strip() if pd.notna(row.get("ANIO_PUBLICACION")) else ""
        
        # Eliminar decimales si pandas lee el año o isbn como flotante
        if isbn_raw.endswith(".0"): isbn_raw = isbn_raw[:-2]
        if anio.endswith(".0"): anio = anio[:-2]
        
        rec = BookRecord(
            id_registro=str(idx),
            codigo=isbn_raw,
            titulo=titulo,
            autores=autores,
            editorial=editorial,
            anio_publicacion=anio
        )
        records_to_validate.append(rec)

    print(f"Se encontraron {len(records_to_validate)} registros para validar.\n")
    print("Iniciando validación con Groq AI y OpenLibrary/GoogleBooks...")
    
    validator = BookValidator()
    
    # Barra de progreso asíncrona
    ai_sem = asyncio.Semaphore(1)
    async def process_with_progress(rec):
        res = await validator.validate_record(rec, ai_semaphore=ai_sem)
        return res
        
    tasks = [process_with_progress(rec) for rec in records_to_validate]
    resultados = []
    
    for f in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Procesando ISBNs", unit="reg", ncols=80):
        res = await f
        resultados.append(res)
        
    # Cerrar conexión compartida de aiohttp de manera segura
    if hasattr(validator.fetcher, 'close'):
        await validator.fetcher.close()
        
    print("\n\nGenerando archivo Excel de resultados...")
    
    # Crear un DataFrame con los resultados, respetando el orden original a través del código
    resultados_dict = {res.codigo: res for res in resultados}
    
    filas_salida = []
    for rec in records_to_validate:
        # El validador guarda el código limpio en rec.codigo_isbn, pero puede estar vacío
        codigo_clave = rec.codigo_isbn if rec.codigo_isbn else rec.codigo
        # Si falló la regex, el resultado usa el código original limpio, si era "N/A" usa N/A
        if not codigo_clave:
            codigo_clave = "N/A"
            
        res = resultados_dict.get(codigo_clave)
        if not res:
            res = resultados_dict.get(rec.codigo, None)
            
        fila = {
            "ISBN Original": rec.codigo,
            "Código Validado": res.codigo if res else "",
            "COINCIDE (IA)": res.coincide if res else "No",
            "Datos Oficiales (Internet)": res.publicacion_encontrada if res else "",
            "Tus Datos (Ingresados)": res.datos_registrados if res else "",
            "Observaciones IA": res.observaciones if res else "Error desconocido"
        }
        filas_salida.append(fila)

    df_out = pd.DataFrame(filas_salida)
    
    # Guardar con xlsxwriter y formato
    with pd.ExcelWriter(archivo_salida, engine='xlsxwriter') as writer:
        df_out.to_excel(writer, index=False, sheet_name='Validacion')
        workbook = writer.book
        worksheet = writer.sheets['Validacion']
        
        # Formatos
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BC',
            'border': 1
        })
        
        formato_si = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100', 'border': 1})
        formato_no = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006', 'border': 1})
        formato_default = workbook.add_format({'border': 1, 'text_wrap': True, 'valign': 'top'})
        
        # Ancho de columnas
        worksheet.set_column('A:A', 20)
        worksheet.set_column('B:B', 20)
        worksheet.set_column('C:C', 15)
        worksheet.set_column('D:E', 45)
        worksheet.set_column('F:F', 50)
        
        for col_num, value in enumerate(df_out.columns.values):
            worksheet.write(0, col_num, value, header_format)
            
        for row_num in range(len(df_out)):
            coincide_val = str(df_out.iloc[row_num]['COINCIDE (IA)']).strip().lower()
            if coincide_val == 'sí' or coincide_val == 'si':
                fmt = formato_si
            else:
                fmt = formato_no
                
            worksheet.write(row_num + 1, 2, df_out.iloc[row_num]['COINCIDE (IA)'], fmt)
            
            # Escribir el resto con formato default
            worksheet.write(row_num + 1, 0, df_out.iloc[row_num]['ISBN Original'], formato_default)
            worksheet.write(row_num + 1, 1, df_out.iloc[row_num]['Código Validado'], formato_default)
            worksheet.write(row_num + 1, 3, df_out.iloc[row_num]['Datos Oficiales (Internet)'], formato_default)
            worksheet.write(row_num + 1, 4, df_out.iloc[row_num]['Tus Datos (Ingresados)'], formato_default)
            worksheet.write(row_num + 1, 5, df_out.iloc[row_num]['Observaciones IA'], formato_default)
            
    print(f"\n¡Éxito! Los resultados se han guardado en: '{archivo_salida}'")


if __name__ == "__main__":
    # Evitar RuntimeError en Windows
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
