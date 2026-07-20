import re
import asyncio
import hashlib
from difflib import SequenceMatcher
from typing import List, Dict, Any, Union
from .models import PublicationRecord, ValidationResult, AIValidationReport
from .api_clients import MetadataFetcher

class SimilarityEngine:
    """
    Motor matemático local para comparar cadenas de texto ignorando mayúsculas, signos y acentos.
    """
    def _normalize_text(self, text: str) -> str:
        if not text:
            return ""
        # Convertir a minúsculas
        text = str(text).lower()
        # Eliminar tildes básicas (simplificado para no depender de librerías extra como unidecode)
        replacements = (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ü", "u"), ("ñ", "n"))
        for a, b in replacements:
            text = text.replace(a, b)
        # Eliminar todo lo que no sea letra o número
        text = re.sub(r'[^\w\s]', '', text)
        # Eliminar espacios dobles
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def compare_titles(self, title1: str, title2: str, threshold: float = 0.85) -> dict:
        norm1 = self._normalize_text(title1)
        norm2 = self._normalize_text(title2)
        
        if not norm1 or not norm2:
            return {"coincide": "No", "similitud": 0.0, "observaciones": "Uno de los títulos está en blanco."}
            
        ratio = SequenceMatcher(None, norm1, norm2).ratio()
        similitud_porcentaje = round(ratio * 100, 2)
        
        coincide = "Sí" if ratio >= threshold else "No"
        
        if coincide == "Sí":
            obs = f"Aprobado: El título coincide matemáticamente al {similitud_porcentaje}%."
        else:
            obs = f"Rechazado: El título registrado es muy distinto al oficial (Similitud: {similitud_porcentaje}%)."
            
        return {"coincide": coincide, "similitud": similitud_porcentaje, "observaciones": obs}


class PublicationValidator:
    """
    Main Orchestrator for validating DOIs and ISSNs using Mathematical Similarity (No AI).
    """
    def __init__(self, fetcher: MetadataFetcher = None, threshold: float = 0.85):
        self.fetcher = fetcher or MetadataFetcher()
        self.engine = SimilarityEngine()
        self.threshold = threshold
        self._cache: Dict[str, ValidationResult] = {}
        
    def _clean_code(self, code: Union[str, None]) -> str:
        return code.strip() if code else ""

    def _limpiar_codigo(self, raw: str) -> str:
        if not raw: return ""
        cleaned = str(raw).strip()
        if "doi.org/" in cleaned:
            cleaned = cleaned.split("doi.org/")[-1]
        
        cleaned = re.sub(r'(?i)^doi:\s*', '', cleaned)
        cleaned = re.sub(r'(?i)^issn:\s*', '', cleaned)
        
        if ":" in cleaned and not cleaned.startswith("10."):
            partes = cleaned.split(":", 1)
            if len(partes) > 1 and (partes[1].strip().startswith("10.") or re.match(r'^\d', partes[1].strip())):
                cleaned = partes[1].strip()
                
        cleaned = re.sub(r'[^a-zA-Z0-9.\-/:_;()]', '', cleaned)
        return cleaned

    def _is_valid_doi_format(self, doi: str) -> bool:
        if not doi:
            return False
        return bool(re.match(r'^10\.\d{4,9}/[-._;()/:A-Z0-9]+$', doi, re.IGNORECASE))
        
    def _is_valid_issn_format(self, issn: str) -> bool:
        if not issn:
            return False
        return bool(re.match(r'^\d{4}-?\d{3}[\dxX]$', issn, re.IGNORECASE))

    async def validate_record(self, record: Union[Dict[str, Any], PublicationRecord]) -> ValidationResult:
        if isinstance(record, dict):
            record = PublicationRecord(**record)
            
        doi_limpio = self._clean_code(record.codigo_doi)
        issn_limpio = self._clean_code(record.codigo_issn)
        
        record_str = f"{record.titulo}_{doi_limpio}_{issn_limpio}"
        record_hash = hashlib.md5(record_str.encode('utf-8')).hexdigest()
        cache_key = f"code_{record_hash}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        if doi_limpio:
            if self._is_valid_doi_format(doi_limpio):
                record.codigo_doi = doi_limpio
                try:
                    official_data = await self.fetcher.fetch_doi_metadata(doi_limpio)
                except Exception:
                    official_data = None
                    
                if not official_data:
                    result = ValidationResult(
                        codigo=doi_limpio,
                        publicacion_encontrada="No se encontró en la Base de Datos",
                        datos_registrados=record.titulo or "Desconocido",
                        coincide="No",
                        observaciones="El DOI es inválido o no existe en Crossref.",
                        similitud=0.0
                    )
                else:
                    official_title = official_data.get("titulo", "")
                    user_title = record.titulo or ""
                    
                    comp = self.engine.compare_titles(user_title, official_title, self.threshold)
                    
                    result = ValidationResult(
                        codigo=doi_limpio,
                        publicacion_encontrada=official_title,
                        datos_registrados=user_title,
                        coincide=comp["coincide"],
                        observaciones=comp["observaciones"],
                        similitud=comp["similitud"]
                    )
                    
                self._cache[cache_key] = result
                return result
            else:
                return ValidationResult(
                    codigo=doi_limpio,
                    publicacion_encontrada="No se consultó",
                    datos_registrados=record.titulo or "Desconocido",
                    coincide="No",
                    observaciones="Error de formato: El DOI es incorrecto.",
                    similitud=0.0
                )
                
        elif issn_limpio:
            if self._is_valid_issn_format(issn_limpio):
                record.codigo_issn = issn_limpio
                try:
                    official_data = await self.fetcher.fetch_issn_metadata(issn_limpio)
                except Exception:
                    official_data = None
                    
                if not official_data:
                    result = ValidationResult(
                        codigo=issn_limpio,
                        publicacion_encontrada="No se encontró en la Base de Datos",
                        datos_registrados=record.titulo or "Desconocido",
                        coincide="No",
                        observaciones="El ISSN es inválido o no existe en los catálogos.",
                        similitud=0.0
                    )
                else:
                    official_title = official_data.get("titulo", "")
                    user_title = record.titulo or ""
                    
                    comp = self.engine.compare_titles(user_title, official_title, self.threshold)
                    
                    result = ValidationResult(
                        codigo=issn_limpio,
                        publicacion_encontrada=official_title,
                        datos_registrados=user_title,
                        coincide=comp["coincide"],
                        observaciones=comp["observaciones"],
                        similitud=comp["similitud"]
                    )
                    
                self._cache[cache_key] = result
                return result
            else:
                return ValidationResult(
                    codigo=issn_limpio,
                    publicacion_encontrada="No se consultó",
                    datos_registrados=record.titulo or "Desconocido",
                    coincide="No",
                    observaciones="Error de formato: El ISSN es incorrecto.",
                    similitud=0.0
                )
                
        else:
            return ValidationResult(
                codigo="N/A",
                publicacion_encontrada="No se consultó",
                datos_registrados=record.titulo or "Desconocido",
                coincide="No",
                observaciones="No se proporcionó ningún DOI o ISSN.",
                similitud=0.0
            )

    async def validate_batch(self, records: List[Union[Dict[str, Any], PublicationRecord]]) -> AIValidationReport:
        # Ya no requerimos un semáforo artificial (ai_sem) porque ya no usamos Groq.
        # Enviaremos las peticiones concurrentemente de a 20 a la vez para cuidar OpenAlex/Crossref.
        sem = asyncio.Semaphore(20)
        
        async def wrap_validate(rec):
            async with sem:
                return await self.validate_record(rec)
                
        tasks = [wrap_validate(rec) for rec in records]
        results = await asyncio.gather(*tasks)
        
        if hasattr(self.fetcher, 'close'):
            await self.fetcher.close()
            
        return AIValidationReport(resultados=list(results))
