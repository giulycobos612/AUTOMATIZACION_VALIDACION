import json
import os

def create_colab_notebook():
    # 1. Leer el código fuente original
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.join(base_dir, 'src')
    
    with open(os.path.join(src_dir, 'models.py'), 'r', encoding='utf-8') as f:
        models_code = f.read()
        
    with open(os.path.join(src_dir, 'api_clients.py'), 'r', encoding='utf-8') as f:
        api_clients_code = f.read()
        
    with open(os.path.join(src_dir, 'ai_agent.py'), 'r', encoding='utf-8') as f:
        ai_agent_code = f.read()
        # Eliminar imports relativos
        ai_agent_code = ai_agent_code.replace('from .models import PublicationRecord, ValidationResult', '')
        
    with open(os.path.join(src_dir, 'validator.py'), 'r', encoding='utf-8') as f:
        validator_code = f.read()
        # Eliminar imports relativos
        validator_code = validator_code.replace('from .models import PublicationRecord, ValidationResult, AIValidationReport', '')
        validator_code = validator_code.replace('from .api_clients import MetadataFetcher', '')
        validator_code = validator_code.replace('from .ai_agent import AIAgent', '')
        # Eliminar el main de test
        validator_code = validator_code.split('if __name__ == "__main__":')[0]

    # 2. Construir la Celda 2 (El Cerebro)
    cell_2_code = f"""
# ==========================================
# CELDA 2: EL CEREBRO DE VALIDACIÓN
# Ejecuta esta celda para cargar el motor de IA
# ==========================================
import nest_asyncio
nest_asyncio.apply()
import os
import json
import re
import asyncio
import aiohttp
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import groq
import hashlib

{models_code.replace('from pydantic import BaseModel, Field', '').replace('from typing import Optional, List', '')}

{api_clients_code.replace('import aiohttp', '').replace('import asyncio', '').replace('from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type', '').replace('from typing import Optional, Dict, Any', '')}

{ai_agent_code.replace('import os', '').replace('import json', '').replace('from pydantic import BaseModel', '').replace('from typing import Dict, Any, Optional', '').replace('from tenacity import retry, stop_after_attempt, wait_exponential', '').replace('import groq', '')}

{validator_code.replace('import re', '').replace('import asyncio', '').replace('import tenacity', '').replace('from typing import List, Dict, Any, Union', '')}
"""

    # 3. Construir la Celda 3 (Ejecución y Subida)
    cell_3_code = """
# ==========================================
# CELDA 3: INTERFAZ DE USUARIO Y EJECUCIÓN
# Ejecuta esta celda para subir tu Excel y validar
# ==========================================
from google.colab import files
import pandas as pd
import io
import time
import getpass

print("=== VALIDADOR DE DOI E ISSN (GOOGLE COLAB) ===")
print("Este proceso analizará los registros UNO POR UNO para evitar bloqueos por límites de uso gratuito.\\n")

# 1. Pedir API Key de Groq
api_key = getpass.getpass("🔑 Ingresa tu GROQ API KEY (Oculta por seguridad) y presiona ENTER: ")
os.environ["GROQ_API_KEY"] = api_key

print("\\n📂 Sube tu archivo Excel (debe tener las columnas TIPO, CODIGO, TITULO, AUTORES_EDITORIAL)")
uploaded = files.upload()

if not uploaded:
    print("❌ No se subió ningún archivo.")
else:
    # Tomar el primer archivo subido
    filename = list(uploaded.keys())[0]
    df = pd.read_excel(io.BytesIO(uploaded[filename]))
    print(f"✅ Archivo cargado: {len(df)} registros encontrados.")
    
    # Preparar registros
    registros_a_procesar = []
    for idx, row in df.iterrows():
        tipo = str(row.get("TIPO", "")).strip().upper()
        codigo = str(row.get("CODIGO", "")).strip()
        titulo = str(row.get("TITULO", "")).strip() if pd.notna(row.get("TITULO", "")) else ""
        autores = str(row.get("AUTORES_EDITORIAL", "")).strip() if pd.notna(row.get("AUTORES_EDITORIAL", "")) else ""
        
        if tipo not in ["DOI", "ISSN"]:
            tipo = "DOI" if "10." in codigo else "ISSN"
            
        registro = {
            "id_registro": f"Fila_{idx+2}",
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
        
    resultados_list = []
    total = len(registros_a_procesar)
    
    async def procesar_lote_seguro():
        validador = PublicationValidator()
        print("\\n🚀 Iniciando validación inteligente, por favor espera...")
        
        for idx, rec in enumerate(registros_a_procesar):
            print(f"🔎 Analizando ({idx+1}/{total}): {rec.get('codigo_doi') or rec.get('codigo_issn')}...", end="")
            try:
                # PAUSA CONTROLADA PARA NO SATURAR GROQ (EVITA EL ERROR DE CONNECTION/RATE LIMIT)
                await asyncio.sleep(3.2)
                res = await validador.validate_record(rec)
                resultados_list.append(res)
                print(f" [OK: {res.coincide}]")
            except Exception as e:
                print(f" [ERROR: {str(e)}]")
                resultados_list.append(ValidationResult(
                    codigo=rec.get('codigo_doi') or rec.get('codigo_issn'),
                    publicacion_encontrada="Error",
                    datos_registrados=rec.get('titulo') or "Desconocido",
                    coincide="No",
                    observaciones=f"Fallo técnico: {str(e)}"
                ))
                
        # Cerrar conexión
        if hasattr(validador.fetcher, 'close'):
            await validador.fetcher.close()
            
    # Ejecutar proceso
    asyncio.run(procesar_lote_seguro())
    
    # Preparar Excel de salida
    print("\\n💾 Generando archivo de resultados...")
    df_out = df.copy()
    df_out["COINCIDE_IA"] = [res.coincide for res in resultados_list]
    df_out["OBSERVACIONES_IA"] = [res.observaciones for res in resultados_list]
    df_out["DATOS_OFICIALES"] = [res.publicacion_encontrada for res in resultados_list]
    
    output_filename = f"Resultados_Colab_{filename}"
    df_out.to_excel(output_filename, index=False)
    
    print(f"🎉 ¡Proceso finalizado! Descargando {output_filename}...")
    files.download(output_filename)
"""

    notebook = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# Validador Inteligente de DOI e ISSN\n",
                    "**Este cuaderno procesa archivos Excel para validar códigos contra bases de datos oficiales.**\n",
                    "Ejecuta las celdas en orden presionando el botón `Play`."
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "!pip install -q groq pydantic aiohttp pandas openpyxl tenacity nest_asyncio"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    cell_2_code
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    cell_3_code
                ]
            }
        ],
        "metadata": {
            "colab": {
                "name": "Validador_DOI_ISSN_Colab.ipynb",
                "provenance": []
            },
            "kernelspec": {
                "display_name": "Python 3",
                "name": "python3"
            },
            "language_info": {
                "name": "python"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 0
    }
    
    # Guardar en la raíz
    output_path = os.path.join(base_dir, 'Validador_DOI_ISSN_Colab.ipynb')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=2, ensure_ascii=False)
        
    print(f"Cuaderno generado exitosamente en: {output_path}")

if __name__ == "__main__":
    create_colab_notebook()
