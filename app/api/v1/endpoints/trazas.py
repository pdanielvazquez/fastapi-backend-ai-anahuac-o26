from fastapi import APIRouter, Query, status

from app.schemas.traza import TrazaAgenteCrear, TrazaAgenteRespuesta
from app.services.traza_service import traza_service

router = APIRouter()


@router.post(
    "/",
    response_model=TrazaAgenteRespuesta,
    status_code=status.HTTP_201_CREATED,
)
async def registrar_evento_agente(traza: TrazaAgenteCrear) -> dict:
    return await traza_service.registrar_traza(traza)


@router.get(
    "/sesion/{session_id}",
    response_model=list[TrazaAgenteRespuesta],
    status_code=status.HTTP_200_OK,
)
async def obtener_trazas_por_sesion(
    session_id: str,
    limit: int = Query(default=500, ge=1, le=1000),
) -> list[dict]:
    return await traza_service.obtener_trazas_sesion(session_id, limit=limit)
