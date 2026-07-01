import os
import json
from pydantic import BaseModel
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential
from .models import PublicationRecord, ValidationResult

class AIManager:
    """
    Manages interactions with the AI Model asynchronusly to perform the validation using standard prompts.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            pass
            
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
        except ImportError:
            self.client = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def validate_doi(self, record: PublicationRecord, fetched_data: Optional[Dict[str, Any]]) -> ValidationResult:
        if not self.client:
            return ValidationResult(
                codigo=record.codigo_doi or "",
                publicacion_encontrada="Error de Configuración",
                datos_registrados=record.titulo or "Desconocido",
                coincide="No",
                observaciones="Fallo en la llamada a la IA: google-genai no está instalado o falta la API key."
            )
            
        system_prompt = (
            "Actúa como un especialista en gestión de información científica, metadatos bibliográficos y validación de identificadores digitales. "
            "Tu objetivo es verificar que los códigos DOI registrados en una matriz o base de datos correspondan correctamente con las publicaciones académicas asociadas.\n"
            "Compara los datos registrados por el usuario con los datos oficiales encontrados."
        )
        
        user_prompt = f"""
        Datos Registrados en nuestra base de datos:
        - Título: {record.titulo}
        - Autores: {record.autores}
        - Año: {record.anio_publicacion}
        - Revista/Editorial: {record.revista_editorial}
        - Tipo: {record.tipo_publicacion}
        - DOI: {record.codigo_doi}
        
        Datos Encontrados Oficialmente (Crossref/Otros):
        {json.dumps(fetched_data, indent=2, ensure_ascii=False) if fetched_data else "No se encontró el DOI o el DOI es inválido."}
        
        Evalúa:
        1. Correspondencia del título y autores.
        2. Coincidencia del año y revista/editorial.
        3. Identifica inconsistencias (inexistente, asignado a otra publicación, diferencias, errores de tipeo).
        """

        try:
            # Async client generation with strict structured output
            response = await self.client.aio.models.generate_content(
                model='gemini-2.5-flash',
                contents=[system_prompt, user_prompt],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": ValidationResult
                }
            )
            data = json.loads(response.text)
            return ValidationResult(**data)
        except Exception as e:
            return ValidationResult(
                codigo=record.codigo_doi or "",
                publicacion_encontrada="Error en validación IA",
                datos_registrados="Error",
                coincide="No",
                observaciones=f"Fallo en la llamada a la IA: {str(e)}"
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def validate_issn(self, record: PublicationRecord, fetched_data: Optional[Dict[str, Any]]) -> ValidationResult:
        if not self.client:
            return ValidationResult(
                codigo=record.codigo_issn or "",
                publicacion_encontrada="Error de Configuración",
                datos_registrados=record.titulo or "Desconocido",
                coincide="No",
                observaciones="Fallo en la llamada a la IA: google-genai no está instalado o falta la API key."
            )
            
        system_prompt = (
            "Actúa como un especialista en gestión de información científica y validación bibliográfica. "
            "Tu objetivo es verificar que los códigos ISSN registrados correspondan correctamente con la publicación académica asociada."
        )
        
        user_prompt = f"""
        Datos Registrados:
        - Título/Revista: {record.titulo}
        - Revista/Editorial: {record.revista_editorial}
        - ISSN: {record.codigo_issn}
        
        Datos Encontrados Oficialmente:
        {json.dumps(fetched_data, indent=2, ensure_ascii=False) if fetched_data else "No se encontró el ISSN o el formato es inválido."}
        
        Evalúa si la revista o serie registrada coincide con el ISSN. Detecta errores de formato (falta de guión), o si es otra revista.
        """

        try:
            # Async client generation with strict structured output
            response = await self.client.aio.models.generate_content(
                model='gemini-2.5-flash',
                contents=[system_prompt, user_prompt],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": ValidationResult
                }
            )
            data = json.loads(response.text)
            return ValidationResult(**data)
        except Exception as e:
            return ValidationResult(
                codigo=record.codigo_issn or "",
                publicacion_encontrada="Error",
                datos_registrados="Error",
                coincide="No",
                observaciones=f"Fallo en la llamada a la IA: {str(e)}"
            )
