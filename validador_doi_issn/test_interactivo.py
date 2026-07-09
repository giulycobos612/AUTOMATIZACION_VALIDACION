import asyncio
import os
import sys

# Añadir el directorio actual al path para que encuentre la carpeta 'src'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.validator import PublicationValidator

async def main():
    print("\n" + "="*60)
    print("BIENVENIDO AL VALIDADOR INTERACTIVO DE DOI/ISSN")
    print("="*60 + "\n")
    
    # Verificar llave de API
    if not os.environ.get("GROQ_API_KEY"):
        print("ADVERTENCIA: No se ha detectado la variable GROQ_API_KEY.")
        print("Por favor, pega tu llave de Groq aqui (empieza con gsk_): ", end="")
        key = input().strip()
        if not key:
            print("Error: Se requiere una llave para continuar.")
            return
        os.environ["GROQ_API_KEY"] = key
    
    validador = PublicationValidator()
    
    while True:
        print("\n" + "-"*50)
        tipo = input("Que deseas validar? (Escribe 'doi' o 'issn', o 'salir' para terminar): ").strip().lower()
        
        if tipo == 'salir':
            print("Programa finalizado. Hasta luego.")
            break
        elif tipo not in ['doi', 'issn']:
            print("Opcion no valida. Por favor escribe 'doi' o 'issn'.")
            continue
            
        codigo = input(f"Ingresa el codigo {tipo.upper()} a validar: ").strip()
        
        if tipo == 'doi':
            print("\n-- COMPLETANDO DATOS DEL ARTICULO (DOI) --")
            titulo = input("Ingresa el Título del ARTICULO (opcional, Enter para omitir): ").strip()
            autores = input("Ingresa los Autores del ARTICULO (opcional, Enter para omitir): ").strip()
            revista = input("Ingresa el Nombre de la REVISTA donde se publico (opcional, Enter para omitir): ").strip()
        else:
            print("\n-- COMPLETANDO DATOS DE LA PUBLICACION (ISSN) --")
            titulo = input("Ingresa el Nombre de la REVISTA o PUBLICACION (opcional, Enter para omitir): ").strip()
            revista = input("Ingresa la EDITORIAL o Entidad responsable (opcional, Enter para omitir): ").strip()
            autores = ""
        
        # Construir el registro simulando lo que enviaria tu plataforma
        registro = {
            "id_registro": "prueba_manual_1",
            "tipo_publicacion": "ARTICULO" if tipo == 'doi' else "REVISTA",
            "titulo": titulo if titulo else "Desconocido",
            "autores": autores if autores else "Desconocidos",
            "anio_publicacion": "",
            "revista_editorial": revista
        }
        
        if tipo == 'doi':
            registro["codigo_doi"] = codigo
            registro["codigo_issn"] = ""
        else:
            registro["codigo_doi"] = ""
            registro["codigo_issn"] = codigo
            
        print("\nConectando con bases de datos y procesando con Inteligencia Artificial... (Por favor espera)")
        
        # Ejecutar validacion
        resultado = await validador.validate_record(registro)
        
        print("\n--- VALIDACION COMPLETADA ---")
        print("="*60)
        print(f"Codigo Consultado: {resultado.codigo}")
        print(f"COINCIDE?:         {resultado.coincide}")
        print(f"Observaciones IA:  {resultado.observaciones}")
        print("-"*60)
        print(f"Datos Oficiales (Internet): {resultado.publicacion_encontrada}")
        print(f"Tus Datos (Ingresados)    : {resultado.datos_registrados}")
        print("="*60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSaliendo del programa...")
