from pydantic import BaseModel, Field


class ValidacionInscripcionRequest(BaseModel):
    alumno_id: str = Field(
        min_length=1,
        max_length=128,
        description="ID del individuo Alumno en la ontología",
        examples=["alumno_001"],
    )
    materia_id: str = Field(
        min_length=1,
        max_length=128,
        description="ID del individuo Materia en la ontología",
        examples=["materia_001"],
    )
    agente_solicitante: str = Field(
        default="AgenteValidadorSemantico",
        min_length=1,
        max_length=128,
        description="Nombre del agente CrewAI que solicita la validación",
    )
    session_id: str = Field(
        default="validacion-semantica",
        min_length=1,
        max_length=128,
        description="Identificador de sesión para la traza de auditoría",
    )


class ValidacionSemanticaResponse(BaseModel):
    es_valido: bool = Field(description="Dictamen de consistencia lógica")
    mensaje: str = Field(description="Explicación del razonador")
    relaciones_inferidas: list[str] = Field(
        default_factory=list,
        description="Relaciones de inscripción conocidas después de inferir",
    )
    tiempo_ejecucion_ms: float = Field(
        ge=0,
        description="Tiempo consumido por el razonador HermiT",
    )
