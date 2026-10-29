from datetime import datetime, timezone
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PyObjectId = Annotated[str, BeforeValidator(str)]


class TrazaAgenteCrear(BaseModel):
    session_id: str = Field(..., description="ID único del flujo de trabajo de la Crew")
    agente_rol: str = Field(..., description="Rol del agente en CrewAI")
    herramienta_usada: str | None = Field(
        default=None,
        description="Nombre de la herramienta invocada",
    )
    entrada_query: str = Field(..., description="Prompt o parámetro de entrada")
    respuesta_salida: str = Field(..., description="Resultado o decisión del agente")
    exito: bool = Field(
        default=True,
        description="Indica si la acción se ejecutó sin errores",
    )
    metadatos: dict[str, Any] = Field(
        default_factory=dict,
        description="Métricas de tiempo, tokens u otros datos de ejecución",
    )


class TrazaAgenteRespuesta(TrazaAgenteCrear):
    id: PyObjectId | None = Field(default=None, alias="_id")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(populate_by_name=True)
