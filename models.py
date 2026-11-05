from pydantic import BaseModel, Field, ConfigDict, GetCoreSchemaHandler
from pydantic_core import core_schema
from typing import List, Optional, Any
from datetime import datetime
from bson import ObjectId


class PyObjectId(str):
    """
    Adaptador de tipo personalizado para mapear los ObjectId de MongoDB (BSON)
    a cadenas de texto compatibles con JSON en Pydantic v2.
    """
    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, _handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(ObjectId),
                core_schema.str_schema(),
            ]),
            serialization=core_schema.plain_serializer_function_ser_schema(lambda x: str(x)),
        )


# ==========================================
# ESQUEMAS CRUD BASE
# ==========================================

class AlumnoBase(BaseModel):
    estudiante_id: str = Field(..., description="Matrícula única del alumno, ej. al_001")
    nombre: str = Field(..., description="Nombre completo del alumno")
    edad: int = Field(..., ge=15, le=100)
    genero: str = Field(..., description="masculino / femenino")
    peso: float = Field(..., description="Peso en kg")
    estatus: str = Field(default="Activo")
    clase_ontologica: str = Field(default="Alumno")


class AlumnoCreate(AlumnoBase):
    pass


class AlumnoResponse(AlumnoBase):
    id: PyObjectId = Field(alias="_id")
    iri: str = Field(..., description="IRI semántico unívoco dentro de la ontología")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )


class ProfesorBase(BaseModel):
    profesor_id: str = Field(..., description="Identificador único del profesor, ej. prof_001")
    nombre: str = Field(..., description="Nombre completo")
    categoria: str = Field(default="Titular")
    clase_ontologica: str = Field(default="Profesor")


class ProfesorCreate(ProfesorBase):
    pass


class ProfesorResponse(ProfesorBase):
    id: PyObjectId = Field(alias="_id")
    iri: str = Field(..., description="IRI semántico unívoco")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )


class MateriaBase(BaseModel):
    materia_id: str = Field(..., description="Clave de la materia, ej. mat_001")
    nombre_materia: str = Field(..., description="Nombre de la asignatura")
    creditos: int = Field(..., ge=1, le=20)
    clase_ontologica: str = Field(default="Materia")


class MateriaCreate(MateriaBase):
    pass


class MateriaResponse(MateriaBase):
    id: PyObjectId = Field(alias="_id")
    iri: str = Field(..., description="IRI semántico unívoco")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )


# ==========================================
# ESQUEMAS PARA VALIDACIÓN SEMÁNTICA HÍBRIDA
# ==========================================

class SolicitudInscripcion(BaseModel):
    estudiante_id: str = Field(..., description="Identificador del alumno")
    materia_id: str = Field(..., description="Identificador de la materia")
    profesor_id: str = Field(..., description="Identificador del profesor titular")


class ResultadoValidacionSemantica(BaseModel):
    es_valido: bool
    mensaje: str
    detalles_razonador: List[str] = []
    tiempo_razonamiento_ms: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TrazaAuditoria(BaseModel):
    solicitud: SolicitudInscripcion
    resultado: ResultadoValidacionSemantica
    agente_emisor: str = "Agente_Validador_Semantico"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
