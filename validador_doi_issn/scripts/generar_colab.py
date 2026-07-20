import json
import os

def create_colab_notebook():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.join(base_dir, 'src')
    
    with open(os.path.join(src_dir, 'models.py'), 'r', encoding='utf-8') as f:
        models_code = f.read()
        
    with open(os.path.join(src_dir, 'api_clients.py'), 'r', encoding='utf-8') as f:
        api_clients_code = f.read()
        
    with open(os.path.join(src_dir, 'validator.py'), 'r', encoding='utf-8') as f:
        validator_code = f.read()
        validator_code = validator_code.replace('from .models import PublicationRecord, ValidationResult, AIValidationReport', '')
        validator_code = validator_code.replace('from .api_clients import MetadataFetcher', '')

    cell_2_code = f"""
# ==========================================
# CELDA 2: EL CEREBRO DE VALIDACIÓN MATEMÁTICO
# ==========================================
import nest_asyncio
nest_asyncio.apply()
import os
import re
import asyncio
import aiohttp
import hashlib
from difflib import SequenceMatcher
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

{models_code.replace('from pydantic import BaseModel, Field', '').replace('from typing import Optional, List', '')}

{api_clients_code.replace('import aiohttp', '').replace('import asyncio', '').replace('from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type', '').replace('from typing import Optional, Dict, Any', '')}

{validator_code.replace('import re', '').replace('import asyncio', '').replace('import hashlib', '').replace('from difflib import SequenceMatcher', '').replace('from typing import List, Dict, Any, Union', '')}
"""

    cell_3_code = """
# ==========================================
# CELDA 3: INTERFAZ DE USUARIO Y EJECUCIÓN
# ==========================================
from google.colab import files
import pandas as pd
import io

print("=== VALIDADOR MATEMÁTICO DE DOI E ISSN (GOOGLE COLAB) ===")
print("\\n📂 Sube tu archivo Excel (debe tener las columnas TIPO, CODIGO, TITULO)")
uploaded = files.upload()

if not uploaded:
    print("❌ No se subió ningún archivo.")
else:
    filename = list(uploaded.keys())[0]
    df = pd.read_excel(io.BytesIO(uploaded[filename]))
    print(f"✅ Archivo cargado: {len(df)} registros encontrados.")
    
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
        
    async def procesar_lote():
        validador = PublicationValidator(threshold=0.85)
        print("\\n🚀 Iniciando validación rápida...")
        report = await validador.validate_batch(registros_a_procesar)
        return report.resultados
            
    resultados_list = asyncio.run(procesar_lote())
    
    print("\\n💾 Generando archivo de resultados...")
    df_out = df.copy()
    df_out["%_SIMILITUD"] = [res.similitud for res in resultados_list]
    df_out["COINCIDE_MATH"] = [res.coincide for res in resultados_list]
    df_out["OBSERVACIONES"] = [res.observaciones for res in resultados_list]
    df_out["TITULO_OFICIAL"] = [res.publicacion_encontrada for res in resultados_list]
    
    output_filename = f"Resultados_Math_Colab_{filename}"
    df_out.to_excel(output_filename, index=False)
    
    print(f"🎉 ¡Proceso finalizado! Descargando {output_filename}...")
    files.download(output_filename)
"""

    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": ["!pip install -q pydantic aiohttp pandas openpyxl tenacity nest_asyncio"]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [cell_2_code]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [cell_3_code]
            }
        ],
        "metadata": {
            "colab": {"name": "Validador_DOI_ISSN_Colab.ipynb", "provenance": []},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"}
        },
        "nbformat": 4,
        "nbformat_minor": 0
    }
    
    output_path = os.path.join(base_dir, 'Validador_DOI_ISSN_Colab.ipynb')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=2, ensure_ascii=False)
        
    print(f"Cuaderno generado exitosamente en: {output_path}")

if __name__ == "__main__":
    create_colab_notebook()
