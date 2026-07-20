from pydantic import BaseModel, Field
from typing import Optional, List

class PublicationRecord(BaseModel):
    id_registro: str = Field(..., description="ID of the record in the matrix")
    tipo_publicacion: Optional[str] = Field(None, description="Type of publication (e.g., ARTICULO, LIBRO)")
    codigo_doi: Optional[str] = Field(None, description="Registered DOI code")
    codigo_issn: Optional[str] = Field(None, description="Registered ISSN code")
    titulo: Optional[str] = Field(None, description="Registered title")
    autores: Optional[str] = Field(None, description="Registered authors")
    anio_publicacion: Optional[str] = Field(None, description="Registered publication year")
    revista_editorial: Optional[str] = Field(None, description="Registered journal or publisher")

class ValidationResult(BaseModel):
    codigo: str = Field(..., description="DOI or ISSN code validated")
    publicacion_encontrada: str = Field(..., description="Details of the publication found in official sources")
    datos_registrados: str = Field(..., description="Details of the registered data")
    coincide: str = Field(..., description="Does it match? 'Sí' or 'No'")
    observaciones: str = Field(..., description="Inconsistencies, missing info, format errors, etc.")
    similitud: float = Field(0.0, description="Percentage of similarity (0.0 to 100.0)")
    
class AIValidationReport(BaseModel):
    resultados: List[ValidationResult]
