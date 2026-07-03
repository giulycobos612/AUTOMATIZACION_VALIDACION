import re
import asyncio
import tenacity
from typing import List, Dict, Any, Union
from .models import PublicationRecord, ValidationResult, AIValidationReport
from .api_clients import MetadataFetcher
from .ai_agent import AIAgent

class PublicationValidator:
    """
    Main Orchestrator for validating DOIs and ISSNs.
    Combines async API fetchers, AI analysis and an in-memory cache.
    """
    def __init__(self, fetcher: MetadataFetcher = None, ai_api_key: str = None):
        self.fetcher = fetcher or MetadataFetcher()
        self.ai_manager = AIAgent(ai_api_key)
        self._cache: Dict[str, ValidationResult] = {}
        
    def _clean_code(self, code: Union[str, None]) -> str:
        return code.strip() if code else ""

    def _limpiar_codigo(self, raw: str) -> str:
        if not raw: return ""
        cleaned = str(raw).strip()
        if "doi.org/" in cleaned:
            cleaned = cleaned.split("doi.org/")[-1]
        
        # Eliminar prefijos comunes que el usuario pueda haber ingresado por error
        cleaned = re.sub(r'(?i)^doi:\s*', '', cleaned)
        cleaned = re.sub(r'(?i)^issn:\s*', '', cleaned)
        
        # Eliminar cualquier prefijo extraño que termine en ":" antes de un número
        if ":" in cleaned and not cleaned.startswith("10."):
            partes = cleaned.split(":", 1)
            if len(partes) > 1 and (partes[1].strip().startswith("10.") or re.match(r'^\d', partes[1].strip())):
                cleaned = partes[1].strip()
                
        cleaned = re.sub(r'[^a-zA-Z0-9.\-/:_;()]', '', cleaned)
        return cleaned

    def _is_valid_doi_format(self, doi: str) -> bool:
        if not doi:
            return False
        # Basic DOI format regex (starts with 10.)
        return bool(re.match(r'^10\.\d{4,9}/[-._;()/:A-Z0-9]+$', doi, re.IGNORECASE))
        
    def _is_valid_issn_format(self, issn: str) -> bool:
        if not issn:
            return False
        # Basic ISSN format (with or without hyphen)
        return bool(re.match(r'^\d{4}-?\d{3}[\dxX]$', issn, re.IGNORECASE))

    async def validate_record(self, record: Union[Dict[str, Any], PublicationRecord], ai_semaphore: asyncio.Semaphore = None) -> ValidationResult:
        if isinstance(record, dict):
            record = PublicationRecord(**record)
            
        doi_limpio = self._clean_code(record.codigo_doi)
        issn_limpio = self._clean_code(record.codigo_issn)
        
        # Generar llave de cache única para este registro que incluya los datos de entrada
        import hashlib
        record_str = f"{record.titulo}_{record.autores}_{record.revista_editorial}"
        record_hash = hashlib.md5(record_str.encode('utf-8')).hexdigest()
        cache_key = f"doi:{doi_limpio}_{record_hash}" if doi_limpio else f"issn:{issn_limpio}_{record_hash}"
        if cache_key in self._cache and not (not doi_limpio and not issn_limpio):
            # print(f"[CACHE HIT] Se obtuvo {cache_key} de la caché.")
            return self._cache[cache_key]
        
        if doi_limpio:
            if self._is_valid_doi_format(doi_limpio):
                record.codigo_doi = doi_limpio
                try:
                    official_data = await self.fetcher.fetch_doi_metadata(doi_limpio)
                except Exception as e:
                    # print(f"Error fetching DOI {doi_limpio} after retries: {e}")
                    official_data = None
                    
                try:
                    if ai_semaphore:
                        async with ai_semaphore:
                            await asyncio.sleep(2.1)
                            result = await self.ai_manager.validate_doi(record, official_data)
                    else:
                        result = await self.ai_manager.validate_doi(record, official_data)
                except tenacity.RetryError as e:
                    ex = e.last_attempt.exception()
                    err_msg = getattr(ex, 'message', str(ex))
                    result = ValidationResult(
                        codigo=doi_limpio,
                        publicacion_encontrada="Error Crítico (IA)",
                        datos_registrados=record.titulo or "Desconocido",
                        coincide="No",
                        observaciones=f"Error al validar con IA tras múltiples reintentos: {err_msg}"
                    )
                except Exception as e:
                    result = ValidationResult(
                        codigo=doi_limpio,
                        publicacion_encontrada="Error Crítico",
                        datos_registrados=record.titulo or "Desconocido",
                        coincide="No",
                        observaciones=f"Error inesperado al validar: {str(e)}"
                    )
                    
                self._cache[cache_key] = result
                return result
            else:
                return ValidationResult(
                    codigo=doi_limpio,
                    publicacion_encontrada="No se consultó",
                    datos_registrados=record.titulo or "Desconocido",
                    coincide="No",
                    observaciones="Error de formato: El DOI contiene caracteres incorrectos, espacios intermedios o no cumple con la estructura estándar (ej. 10.xxxx/yyyy)."
                )
                
        elif issn_limpio:
            if self._is_valid_issn_format(issn_limpio):
                record.codigo_issn = issn_limpio
                try:
                    official_data = await self.fetcher.fetch_issn_metadata(issn_limpio)
                except Exception as e:
                    # print(f"Error fetching ISSN {issn_limpio} after retries: {e}")
                    official_data = None
                    
                try:
                    if ai_semaphore:
                        async with ai_semaphore:
                            await asyncio.sleep(2.1)
                            result = await self.ai_manager.validate_issn(record, official_data)
                    else:
                        result = await self.ai_manager.validate_issn(record, official_data)
                except tenacity.RetryError as e:
                    ex = e.last_attempt.exception()
                    err_msg = getattr(ex, 'message', str(ex))
                    result = ValidationResult(
                        codigo=issn_limpio,
                        publicacion_encontrada="Error Crítico (IA)",
                        datos_registrados=record.titulo or "Desconocido",
                        coincide="No",
                        observaciones=f"Error al validar con IA tras múltiples reintentos: {err_msg}"
                    )
                except Exception as e:
                    result = ValidationResult(
                        codigo=issn_limpio,
                        publicacion_encontrada="Error Crítico",
                        datos_registrados=record.titulo or "Desconocido",
                        coincide="No",
                        observaciones=f"Error inesperado al validar: {str(e)}"
                    )
                    
                self._cache[cache_key] = result
                return result
            else:
                return ValidationResult(
                    codigo=issn_limpio,
                    publicacion_encontrada="No se consultó",
                    datos_registrados=record.titulo or "Desconocido",
                    coincide="No",
                    observaciones="Error de formato: El ISSN contiene caracteres incorrectos, carece de formato o no es un código válido (ej. 1234-5678)."
                )
                
        else:
            return ValidationResult(
                codigo="N/A",
                publicacion_encontrada="No se consultó",
                datos_registrados=record.titulo or "Desconocido",
                coincide="No",
                observaciones="Código inexistente o campo vacío. No se proporcionó ningún DOI o ISSN para validar."
            )

    async def validate_batch(self, records: List[Union[Dict[str, Any], PublicationRecord]]) -> AIValidationReport:
        """
        Validates a batch of records asynchronously, using an AI Semaphore to prevent Groq API Rate Limits.
        """
        # Semáforo para controlar la concurrencia de la IA (evitar 429 Rate Limit en Groq - 30 RPM)
        ai_sem = asyncio.Semaphore(1)
        
        async def wrap_validate(rec):
            res = await self.validate_record(rec, ai_semaphore=ai_sem)
            return res
                
        tasks = [wrap_validate(rec) for rec in records]
        results = await asyncio.gather(*tasks)
        
        # Cerrar conexión compartida de aiohttp de manera segura si se creó
        if hasattr(self.fetcher, 'close'):
            await self.fetcher.close()
            
        return AIValidationReport(resultados=list(results))

# =========================================================================================
# SECCIÓN DE COMENTARIOS: GUÍA DE INTEGRACIÓN PARA EL DESARROLLADOR (VERSIÓN ASÍNCRONA)
# =========================================================================================
# Este módulo está diseñado para producción: Asíncrono, con Caché en Memoria y Reintentos Exponenciales.
# - Tipado Estricto: Usa Pydantic (PublicationRecord, ValidationResult) para evitar errores.
# - Asincronía: Al usar async/await, se debe llamar desde un Event Loop de asyncio.
# 
# Ejemplo de uso e integración rápida en el sistema principal:
# 
# import asyncio
# from src.validator import PublicationValidator
# 
# async def main():
#     # 1. Instanciar el validador (inyectando la llave de la API de IA):
#     validador = PublicationValidator(ai_api_key="AQUI_SU_LLAVE_API_DE_IA")
# 
#     # 2. Pasar el registro crudo proveniente de la base de datos local:
#     registro_db = {
#         "id_registro": "123",
#         "titulo": "Estudio del Genoma",
#         "codigo_doi": "10.1000/xyz123"
#     }
# 
#     # 3. Validar de forma asíncrona (AWAIT es obligatorio):
#     resultado = await validador.validate_record(registro_db)
# 
#     # 4. Guardar o retornar como JSON al sistema:
#     json_listo = resultado.model_dump_json()
#     print(json_listo)
#
# if __name__ == "__main__":
#     asyncio.run(main())
# =========================================================================================

if __name__ == "__main__":
    # Prueba de integración local y comprobación de caché
    async def run_tests():
        validator = PublicationValidator()
        sample_record_1 = {
            "id_registro": "1",
            "tipo_publicacion": "ARTICULO",
            "codigo_doi": "10.3390/microorganisms13030482",
            "titulo": "Molecular Detection of blaTEM and blaSHV Genes in ESBL-Producing Acinetobacter baumannii isolated from Antarctic Soil",
            "autores": "Pazos, C., et al.",
            "anio_publicacion": "2025",
            "revista_editorial": "Microorganisms"
        }
        
        # Test 1: Primera vez que se consulta
        print("--- Ejecutando Prueba 1 (Debe ir a la API/IA) ---")
        result1 = await validator.validate_record(sample_record_1)
        print(result1.model_dump_json(indent=2))
        
        # Test 2: Inmediatamente después, misma consulta para comprobar CACHÉ
        print("\n--- Ejecutando Prueba 2 (Debe ser CACHE HIT) ---")
        result2 = await validator.validate_record(sample_record_1)
        print(result2.model_dump_json(indent=2))

    asyncio.run(run_tests())
