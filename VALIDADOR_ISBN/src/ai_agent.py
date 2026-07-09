import os
import json
import logging
from typing import Dict, Any, Union
import groq
from tenacity import retry, stop_after_attempt, wait_exponential

from src.models import BookRecord, ValidationResult

logger = logging.getLogger(__name__)

class AIAgent:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("No se proporcionó una API KEY de Groq. Defínela en GROQ_API_KEY.")
            
        self.client = groq.AsyncGroq(api_key=self.api_key)
        self.model = "llama-3.1-8b-instant"
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def validate_isbn(self, record: BookRecord, official_data: Union[Dict[str, Any], None]) -> ValidationResult:
        """
        Usa Groq (Llama 3.1) para comparar la data oficial de OpenLibrary/Google Books 
        con lo que el usuario ingresó para el libro.
        """
        if not official_data:
            return ValidationResult(
                codigo=record.codigo_isbn or record.codigo,
                publicacion_encontrada="No se encontró",
                datos_registrados=f"Título: {record.titulo} | Autor: {record.autores} | Editorial: {record.editorial} | Año: {record.anio_publicacion}",
                coincide="No",
                observaciones="El ISBN no fue encontrado en las bases de datos de OpenLibrary ni Google Books."
            )
            
        # Formatear lo que ingresó el usuario
        user_prompt = f"""
        DATOS REGISTRADOS (Ingresados por el usuario):
        - Título: {record.titulo}
        - Autores: {record.autores}
        - Editorial: {record.editorial}
        - Año de Publicación: {record.anio_publicacion}
        
        DATOS OFICIALES (Internet - {official_data.get('fuente')}):
        - Título Oficial: {official_data.get('titulo')}
        - Autores Oficiales: {official_data.get('autores')}
        - Editorial Oficial: {official_data.get('editorial')}
        - Año Oficial: {official_data.get('anio_publicacion')}
        """
        
        system_prompt = (
            "Actúa como un bibliotecólogo experto y validador de datos. "
            "Tu objetivo es comparar los metadatos registrados de un libro con los datos oficiales de internet.\n"
            "REGLAS ESTRICTAS:\n"
            "1. En el campo 'datos_registrados' escribe exactamente el Título, Autor, Editorial y Año que el usuario ingresó.\n"
            "2. En el campo 'publicacion_encontrada' escribe exactamente el Título, Autor, Editorial y Año Oficial obtenidos de internet.\n"
            "3. CRÍTICO: Si el usuario ingresó el Título y coincide con el oficial, evalúa 'coincide' como 'Sí' INCLUSO SI dejó los campos de Autor, Editorial o Año en blanco o como 'Desconocido'. (Un solo campo correcto y coincidente es suficiente para validar el ISBN).\n"
            "4. Evalúa 'coincide' como 'No' SOLAMENTE si la información proporcionada es incorrecta (no tiene nada que ver con el libro real), o si absolutamente TODOS los campos del usuario están en blanco.\n"
            "5. En 'observaciones' explica por qué coinciden o fallan, mencionando si falta información secundaria (como el año o la editorial).\n"
            "DEBES RESPONDER ÚNICAMENTE CON UN JSON VÁLIDO QUE TENGA LA SIGUIENTE ESTRUCTURA:\n"
            '{"codigo": "string", "publicacion_encontrada": "string", "datos_registrados": "string", "coincide": "string (Sí/No)", "observaciones": "string"}'
        )
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
                max_tokens=600
            )
            
            result_text = response.choices[0].message.content
            parsed = json.loads(result_text)
            
            return ValidationResult(
                codigo=record.codigo_isbn or record.codigo,
                publicacion_encontrada=parsed.get("publicacion_encontrada", "Error de parseo"),
                datos_registrados=parsed.get("datos_registrados", "Error de parseo"),
                coincide=parsed.get("coincide", "No"),
                observaciones=parsed.get("observaciones", "Sin observaciones.")
            )
            
        except Exception as e:
            raise e
