from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.entidad import EntidadCrear, EntidadRespuesta
from app.services.entidad_service import entidad_service

router = APIRouter()


@router.get(
    "/{id_referencia}",
    response_model=EntidadRespuesta,
    status_code=status.HTTP_200_OK,
)
async def obtener_entidad(id_referencia: str) -> dict:
    entidad = await entidad_service.obtener_por_id_referencia(id_referencia)
    if entidad is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"La entidad '{id_referencia}' no existe en la base de conocimientos.",
        )
    return entidad


@router.get(
    "/",
    response_model=list[EntidadRespuesta],
    status_code=status.HTTP_200_OK,
)
async def listar_entidades_por_tipo(
    tipo: str = Query(..., description="Tipo de entidad que se desea consultar"),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict]:
    return await entidad_service.listar_por_tipo(tipo, limit=limit)


@router.post(
    "/",
    response_model=EntidadRespuesta,
    status_code=status.HTTP_201_CREATED,
)
async def guardar_entidad(entidad: EntidadCrear) -> dict:
    return await entidad_service.crear_entidad(entidad)
