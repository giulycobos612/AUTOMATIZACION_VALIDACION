import os
import json
from pydantic import BaseModel
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from .models import PublicationRecord, ValidationResult
import groq

class AIAgent:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        try:
            self.client = groq.AsyncGroq(api_key=self.api_key)
        except Exception as e:
            print(f"Error initializing Groq client: {e}")
            self.client = None

    @retry(
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=2, min=5, max=60)
    )
    async def validate_doi(self, record: PublicationRecord, fetched_data: Optional[Dict[str, Any]]) -> ValidationResult:
        if not self.client:
            return ValidationResult(
                codigo=record.codigo_doi or "",
                publicacion_encontrada="Error de Configuración",
                datos_registrados=record.titulo or "Desconocido",
                coincide="No",
                observaciones="Fallo en la llamada a la IA: groq no está instalado o falta la API key."
            )
            
        system_prompt = (
            "Actúa como un especialista en gestión de información científica y validación bibliográfica. "
            "Tu objetivo es verificar que los metadatos registrados (título, autores, etc.) correspondan con los datos oficiales del DOI.\n"
            "REGLAS ESTRICTAS:\n"
            "1. En el campo 'datos_registrados' debes incluir EXACTAMENTE lo que el usuario ingresó (el Título y Autores). No lo alteres.\n"
            "2. En el campo 'publicacion_encontrada' debes incluir el título y autores reales extraídos de los datos oficiales.\n"
            "3. Evalúa 'coincide' como 'Sí' si el título o los autores proporcionados coinciden sustancialmente.\n"
            "4. CRÍTICO: Si el usuario proporcionó solo un campo (ej. solo Título o solo Autores), realiza la validación usando solo ese campo. Si proporcionó ambos, evalúa usando ambos. Si AMBOS están completamente vacíos o dicen 'None'/'Desconocido', DEBES evaluar 'coincide' como 'No' e indicar que faltan datos.\n"
            "5. En 'observaciones' explica en qué coinciden o fallan, detectando errores tipográficos, traducciones, o si falta información.\n"
            "DEBES RESPONDER ÚNICAMENTE CON UN JSON VÁLIDO QUE TENGA LA SIGUIENTE ESTRUCTURA:\n"
            '{"codigo": "string", "publicacion_encontrada": "string", "datos_registrados": "string", "coincide": "string (Sí/No)", "observaciones": "string"}'
        )
        
        user_prompt = f"""
        Datos Registrados (Ingresados por el usuario):
        - Título: {record.titulo}
        - Autores/Editorial: {record.revista_editorial}
        - DOI: {record.codigo_doi}
        
        Datos Encontrados Oficialmente (Crossref/Otros):
        {json.dumps(fetched_data, indent=2, ensure_ascii=False) if fetched_data else "No se encontró el DOI o el DOI es inválido."}
        
        Evalúa y responde SOLO en formato JSON.
        """

        response = await self.client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        return ValidationResult(**data)

    @retry(
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=2, min=5, max=60)
    )
    async def validate_issn(self, record: PublicationRecord, fetched_data: Optional[Dict[str, Any]]) -> ValidationResult:
        if not self.client:
            return ValidationResult(
                codigo=record.codigo_issn or "",
                publicacion_encontrada="Error de Configuración",
                datos_registrados=record.titulo or "Desconocido",
                coincide="No",
                observaciones="Fallo en la llamada a la IA: groq no está instalado o falta la API key."
            )
            
        system_prompt = (
            "Actúa como un especialista en gestión de información científica y validación bibliográfica. "
            "Tu objetivo es verificar que los códigos ISSN registrados correspondan correctamente con la publicación académica asociada.\n"
            "REGLAS ESTRICTAS:\n"
            "1. En el campo 'datos_registrados' debes incluir EXACTAMENTE lo que el usuario ingresó para Título/Revista y para Revista/Editorial.\n"
            "2. En el campo 'publicacion_encontrada' debes incluir el título y editorial oficiales del ISSN.\n"
            "3. Compara si la revista o serie registrada coincide. Si la editorial ingresada no coincide (ej. puso el nombre de un autor), repórtalo en 'observaciones'.\n"
            "4. CRÍTICO: Si el usuario proporcionó solo un campo (ej. solo Título o solo Editorial), realiza la validación usando solo ese campo. Si proporcionó ambos, evalúa usando ambos. Si AMBOS están vacíos o dicen 'None'/'Desconocido', DEBES evaluar 'coincide' como 'No' e indicar que faltan datos.\n"
            "DEBES RESPONDER ÚNICAMENTE CON UN JSON VÁLIDO QUE TENGA LA SIGUIENTE ESTRUCTURA:\n"
            '{"codigo": "string", "publicacion_encontrada": "string", "datos_registrados": "string", "coincide": "string (Sí/No)", "observaciones": "string"}'
        )
        
        user_prompt = f"""
        Datos Registrados:
        - Título/Revista: {record.titulo}
        - Revista/Editorial (Ingresado por usuario): {record.revista_editorial}
        - ISSN: {record.codigo_issn}
        
        Datos Encontrados Oficialmente:
        {json.dumps(fetched_data, indent=2, ensure_ascii=False) if fetched_data else "No se encontró el ISSN o el formato es inválido."}
        
        Evalúa y responde SOLO en formato JSON.
        """

        response = await self.client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        return ValidationResult(**data)
