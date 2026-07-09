from pydantic import BaseModel, Field
from typing import Optional, List, Any

class BookRecord(BaseModel):
    """Estructura de datos para un libro ingresado por el usuario."""
    id_registro: str
    codigo: str = Field(description="Código ISBN bruto (con o sin guiones/letras)")
    tipo: str = "ISBN"
    titulo: Optional[str] = ""
    autores: Optional[str] = ""
    editorial: Optional[str] = ""
    anio_publicacion: Optional[str] = ""
    
    # Campo enriquecido internamente tras la limpieza
    codigo_isbn: Optional[str] = None


class ValidationResult(BaseModel):
    """Respuesta estructurada de la Inteligencia Artificial."""
    codigo: str
    publicacion_encontrada: str = Field(description="Datos oficiales combinados (Título, Autor, Editorial, Año)")
    datos_registrados: str = Field(description="Lo que el usuario ingresó (Título, Autor, Editorial, Año)")
    coincide: str = Field(description="'Sí' o 'No'")
    observaciones: str = Field(description="Razonamiento corto del agente de IA")


class AIValidationReport(BaseModel):
    resultados: List[ValidationResult]
