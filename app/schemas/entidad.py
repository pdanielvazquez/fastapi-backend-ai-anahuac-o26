from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PyObjectId = Annotated[str, BeforeValidator(str)]


class EntidadBase(BaseModel):
    id_referencia: str = Field(
        ..., description="Identificador de dominio (por ejemplo, al_001 o mat_101)"
    )
    nombre: str = Field(..., description="Nombre o etiqueta principal")
    tipo_entidad: str = Field(
        ..., description="Categoría de la entidad (por ejemplo, Alumno o Materia)"
    )
    atributos: dict[str, Any] = Field(
        default_factory=dict,
        description="Atributos de datos dinámicos",
    )
    relaciones: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Relaciones con otras entidades de la base de conocimiento",
    )


class EntidadCrear(EntidadBase):
    pass


class EntidadRespuesta(EntidadBase):
    id: PyObjectId | None = Field(default=None, alias="_id")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "id_referencia": "al_001",
                "nombre": "Daniel Vázquez",
                "tipo_entidad": "Alumno",
                "atributos": {"edad": 22, "promedio": 9.1},
                "relaciones": {"estaInscritoEn": ["mat_001", "mat_002"]},
            }
        },
    )
