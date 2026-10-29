import os

import httpx
from crewai.tools import tool


FASTAPI_BASE_URL = os.getenv(
    "FASTAPI_BASE_URL",
    "http://localhost:8000/api/v1",
).rstrip("/")
SESSION_ID = os.getenv("CREWAI_SESSION_ID", "sesion_demo_001")


def _http_error_message(exc: httpx.HTTPStatusError) -> str:
    return (
        f"Error en la API FastAPI: HTTP {exc.response.status_code} - "
        f"{exc.response.text}"
    )


@tool("Consulta de Base de Datos Operativa")
def consultar_entidad_kb_tool(id_referencia: str) -> str:
    """Consulta una entidad en la base operativa a través de FastAPI."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(
                f"{FASTAPI_BASE_URL}/entidades/{id_referencia}",
            )
            if response.status_code == httpx.codes.NOT_FOUND:
                return f"La entidad '{id_referencia}' no existe en MongoDB."
            response.raise_for_status()
            data = response.json()

            trace_response = client.post(
                f"{FASTAPI_BASE_URL}/trazas/",
                json={
                    "session_id": SESSION_ID,
                    "agente_rol": "Agente_Consultor_KB",
                    "herramienta_usada": "consultar_entidad_kb_tool",
                    "entrada_query": id_referencia,
                    "respuesta_salida": f"Entidad {data['nombre']} recuperada.",
                    "exito": True,
                },
            )
            trace_response.raise_for_status()
            return (
                f"Datos encontrados: {data['nombre']} | "
                f"Tipo: {data['tipo_entidad']} | Atributos: {data['atributos']}"
            )
    except httpx.HTTPStatusError as exc:
        return _http_error_message(exc)
    except httpx.RequestError as exc:
        return f"Error de conexión con el backend FastAPI: {exc}"


@tool("Herramienta de Validación Semántica Ontológica")
def validar_inscripcion_materia_tool(alumno_id: str, materia_id: str) -> str:
    """Valida una inscripción contra la ontología OWL del backend FastAPI."""
    payload = {
        "alumno_id": alumno_id,
        "materia_id": materia_id,
        "agente_solicitante": "AgenteValidadorSemantico",
        "session_id": SESSION_ID,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{FASTAPI_BASE_URL}/validar-semantica",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        dictamen = "autorizada" if data["es_valido"] else "rechazada"
        return (
            f"VALIDADOR SEMÁNTICO: Inscripción {dictamen}. "
            f"{data['mensaje']} "
            f"(Relaciones: {data['relaciones_inferidas']}; "
            f"tiempo: {data['tiempo_ejecucion_ms']} ms)"
        )
    except httpx.HTTPStatusError as exc:
        return _http_error_message(exc)
    except httpx.RequestError as exc:
        return f"Error de comunicación con el backend FastAPI: {exc}"
