import re
import asyncio
from typing import List, Dict, Any, Union
from .models import PublicationRecord, ValidationResult, AIValidationReport
from .api_clients import MetadataFetcher
from .ai_agent import AIManager

class PublicationValidator:
    """
    Main Orchestrator for validating DOIs and ISSNs.
    Combines async API fetchers, AI analysis and an in-memory cache.
    """
    def __init__(self, ai_api_key: str = None):
        self.ai_manager = AIManager(api_key=ai_api_key)
        self.fetcher = MetadataFetcher()
        self._cache: Dict[str, ValidationResult] = {}
        
    def _clean_code(self, code: Union[str, None]) -> str:
        return code.strip() if code else ""

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

    async def validate_record(self, record: Union[Dict[str, Any], PublicationRecord]) -> ValidationResult:
        if isinstance(record, dict):
            record = PublicationRecord(**record)
            
        doi_limpio = self._clean_code(record.codigo_doi)
        issn_limpio = self._clean_code(record.codigo_issn)
        
        # Generar llave de cache única para este registro
        cache_key = f"doi:{doi_limpio}" if doi_limpio else f"issn:{issn_limpio}"
        if cache_key in self._cache and cache_key not in ["doi:", "issn:"]:
            print(f"[CACHE HIT] Se obtuvo {cache_key} de la caché.")
            return self._cache[cache_key]
        
        if doi_limpio:
            if self._is_valid_doi_format(doi_limpio):
                record.codigo_doi = doi_limpio
                try:
                    official_data = await self.fetcher.fetch_doi_metadata(doi_limpio)
                except Exception as e:
                    print(f"Error fetching DOI {doi_limpio} after retries: {e}")
                    official_data = None
                    
                try:
                    result = await self.ai_manager.validate_doi(record, official_data)
                except Exception as e:
                    result = ValidationResult(
                        codigo=doi_limpio,
                        publicacion_encontrada="Error Crítico",
                        datos_registrados=record.titulo or "Desconocido",
                        coincide="No",
                        observaciones=f"Error al validar con IA tras reintentos: {str(e)}"
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
                    print(f"Error fetching ISSN {issn_limpio} after retries: {e}")
                    official_data = None
                    
                try:
                    result = await self.ai_manager.validate_issn(record, official_data)
                except Exception as e:
                    result = ValidationResult(
                        codigo=issn_limpio,
                        publicacion_encontrada="Error Crítico",
                        datos_registrados=record.titulo or "Desconocido",
                        coincide="No",
                        observaciones=f"Error al validar con IA tras reintentos: {str(e)}"
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
        Validates a batch of records asynchronously and concurrently.
        """
        tasks = [self.validate_record(rec) for rec in records]
        results = await asyncio.gather(*tasks)
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
