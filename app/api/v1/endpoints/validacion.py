import time

from fastapi import APIRouter, status
from starlette.concurrency import run_in_threadpool

from app.schemas.traza import TrazaAgenteCrear
from app.schemas.validacion import (
    ValidacionInscripcionRequest,
    ValidacionSemanticaResponse,
)
from app.services.ontology_service import ontology_service
from app.services.traza_service import traza_service


router = APIRouter()


@router.post(
    "/validar-semantica",
    response_model=ValidacionSemanticaResponse,
    status_code=status.HTTP_200_OK,
    tags=["Inferencia Semántica OWL"],
)
@router.post(
    "/validacion/validar-inscripcion",
    response_model=ValidacionSemanticaResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def validar_inscripcion_semantica(
    solicitud: ValidacionInscripcionRequest,
) -> ValidacionSemanticaResponse:
    inicio = time.perf_counter()
    es_valido, mensaje, relaciones = await run_in_threadpool(
        ontology_service.validar_inscripcion_alumno,
        alumno_id=solicitud.alumno_id,
        materia_id=solicitud.materia_id,
    )
    tiempo_total_ms = round((time.perf_counter() - inicio) * 1000, 2)

    await traza_service.registrar_traza(
        TrazaAgenteCrear(
            session_id=solicitud.session_id,
            agente_rol=solicitud.agente_solicitante,
            herramienta_usada="validar_inscripcion_materia_tool",
            entrada_query=f"{solicitud.alumno_id} -> {solicitud.materia_id}",
            respuesta_salida=mensaje,
            exito=es_valido,
            metadatos={
                "accion": "VALIDACION_ONTOLOGICA_INSCRIPCION",
                "alumno_id": solicitud.alumno_id,
                "materia_id": solicitud.materia_id,
                "relaciones_inferidas": relaciones,
                "tiempo_razonamiento_ms": tiempo_total_ms,
            },
        )
    )

    return ValidacionSemanticaResponse(
        es_valido=es_valido,
        mensaje=mensaje,
        relaciones_inferidas=relaciones,
        tiempo_ejecucion_ms=tiempo_total_ms,
    )
