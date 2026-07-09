import asyncio
import re
import hashlib
from typing import List, Dict, Any, Union, Optional
import tenacity

from src.models import BookRecord, ValidationResult, AIValidationReport
from src.api_clients import MetadataFetcher
from src.ai_agent import AIAgent

class BookValidator:
    def __init__(self, ai_api_key: str = None):
        self.fetcher = MetadataFetcher()
        self.ai_manager = AIAgent(api_key=ai_api_key)
        self._cache: Dict[str, ValidationResult] = {}
        
    def _limpiar_codigo(self, raw: str) -> str:
        if not raw: return ""
        cleaned = str(raw).strip()
        
        # Eliminar prefijos que el usuario pueda poner por accidente
        cleaned = re.sub(r'(?i)^isbn(?:-10|-13)?:\s*', '', cleaned)
        
        # Quitar todos los guiones, espacios y caracteres no alfanuméricos (excepto la X que se usa en ISBN-10)
        cleaned = re.sub(r'[^a-zA-Z0-9]', '', cleaned).upper()
        return cleaned

    def _is_valid_isbn_format(self, isbn: str) -> bool:
        if not isbn:
            return False
        # El ISBN debe tener 10 o 13 caracteres, compuestos por dígitos (y opcionalmente X al final para ISBN-10)
        return bool(re.match(r'^(?:\d{9}[\dX]|\d{13})$', isbn))
        
    def _get_cache_key(self, isbn: str, record: BookRecord) -> str:
        data = f"{isbn}_{record.titulo}_{record.autores}_{record.editorial}_{record.anio_publicacion}".encode('utf-8')
        return hashlib.md5(data).hexdigest()

    async def validate_record(self, record: BookRecord, ai_semaphore: Optional[asyncio.Semaphore] = None) -> ValidationResult:
        isbn_limpio = self._limpiar_codigo(record.codigo)
        
        if not isbn_limpio:
            return ValidationResult(
                codigo="N/A",
                publicacion_encontrada="No se consultó",
                datos_registrados=record.titulo or "Desconocido",
                coincide="No",
                observaciones="Código inexistente o campo vacío."
            )
            
        if not self._is_valid_isbn_format(isbn_limpio):
            return ValidationResult(
                codigo=isbn_limpio,
                publicacion_encontrada="No se consultó",
                datos_registrados=record.titulo or "Desconocido",
                coincide="No",
                observaciones="Error de formato: El ISBN debe tener 10 o 13 caracteres (números, sin incluir guiones)."
            )
            
        record.codigo_isbn = isbn_limpio
        cache_key = self._get_cache_key(isbn_limpio, record)
        
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        try:
            official_data = await self.fetcher.fetch_isbn_metadata(isbn_limpio)
        except Exception as e:
            official_data = None
            
        try:
            if ai_semaphore:
                async with ai_semaphore:
                    # Pausa preventiva mínima (30 RPM en Groq = 2s)
                    await asyncio.sleep(2.1)
                    result = await self.ai_manager.validate_isbn(record, official_data)
            else:
                result = await self.ai_manager.validate_isbn(record, official_data)
        except tenacity.RetryError as e:
            ex = e.last_attempt.exception()
            err_msg = getattr(ex, 'message', str(ex))
            result = ValidationResult(
                codigo=isbn_limpio,
                publicacion_encontrada="Error Crítico (IA)",
                datos_registrados=record.titulo or "Desconocido",
                coincide="No",
                observaciones=f"Error al validar con IA: {err_msg}"
            )
        except Exception as e:
            result = ValidationResult(
                codigo=isbn_limpio,
                publicacion_encontrada="Error Crítico",
                datos_registrados=record.titulo or "Desconocido",
                coincide="No",
                observaciones=f"Error inesperado al validar: {str(e)}"
            )
            
        self._cache[cache_key] = result
        return result

    async def validate_batch(self, records: List[Union[Dict[str, Any], BookRecord]]) -> AIValidationReport:
        ai_sem = asyncio.Semaphore(1)
        
        async def wrap_validate(rec):
            return await self.validate_record(rec, ai_semaphore=ai_sem)
                
        tasks = [wrap_validate(rec) for rec in records]
        results = await asyncio.gather(*tasks)
        
        if hasattr(self.fetcher, 'close'):
            await self.fetcher.close()
            
        return AIValidationReport(resultados=list(results))
