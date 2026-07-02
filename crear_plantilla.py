import pandas as pd
import os

def crear_plantilla():
    archivo_salida = "registros_entrada.xlsx"
    
    if os.path.exists(archivo_salida):
        print(f"El archivo '{archivo_salida}' ya existe. Por seguridad, no se sobreescribira.")
        print("Si deseas crear una nueva plantilla, elimina o renombra el archivo existente primero.")
        return

    # Definir las columnas
    columnas = ["TIPO", "CODIGO", "TITULO", "AUTORES_EDITORIAL"]
    
    # Datos de ejemplo
    datos = [
        ["ISSN", "0798-1015", "Revista Espacios", "PUCHAICELA, Carmen G."],
        ["ISSN", "2542-3371", "IUSTITIA SOCIALIS", "Fundacion Koinonia"],
        ["DOI", "10.33936/revbasdelaciencia.v5i2.2741", "Rehabilitación de un paciente con un quiste periapical", "Sonia Patricia Cardenas Macias"],
        ["DOI", "10.1038/s41586-020-2649-2", "AlphaFold: A solution to a 50-year-old grand challenge in biology", "John Jumper"]
    ]
    
    df = pd.DataFrame(datos, columns=columnas)
    
    try:
        df.to_excel(archivo_salida, index=False)
        print("="*60)
        print(f"PLANTILLA CREADA CON EXITO: '{archivo_salida}'")
        print("="*60)
        print("\nAbre el archivo con Excel, borra las filas de ejemplo y pega tus propios registros.")
        print("Luego ejecuta 'py procesador_excel.py' para validarlos todos de golpe.")
    except Exception as e:
        print(f"Error al crear el archivo: {e}")

if __name__ == "__main__":
    crear_plantilla()
