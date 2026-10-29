import httpx
from crewai import Agent, Crew, Task, LLM
from crewai.tools import tool

API_BASE_URL = "http://localhost:8000/api/v1"
SESSION_ID = "sesion_demo_001"

llm = LLM(
    model = "ollama/llama3.2",
    base_url = "http://localhost:11434",
)

@tool("Consulta de Base de Datos Operativa")
def consultar_entidad_kb_tool(id_referencia: str) -> str:
    """Consulta una entidad en la base operativa a través de FastAPI."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(
                f"{API_BASE_URL}/entidades/{id_referencia}",
            )
            if response.status_code == httpx.codes.NOT_FOUND:
                return f"La entidad '{id_referencia}' no existe en MongoDB."
            response.raise_for_status()
            data = response.json()

            trace_response = client.post(
                f"{API_BASE_URL}/trazas/",
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
        return f"Error en la API: HTTP {exc.response.status_code}."
    except httpx.RequestError as exc:
        return f"Error de conexión con el backend FastAPI: {exc}"


agente_consultor = Agent(
    role="Agente Consultor de Base de Datos",
    goal="Recuperar información verídica desde la base operativa.",
    backstory="Especialista en consulta de datos mediante la API FastAPI.",
    tools=[consultar_entidad_kb_tool],
    verbose=True,
    llm = llm
)

tarea_consulta = Task(
    description="Consulta al alumno 'alumno_001' y resume sus datos.",
    expected_output="Resumen del alumno con su nombre y atributos.",
    agent=agente_consultor,
    llm = llm
)

equipo = Crew(
    agents=[agente_consultor],
    tasks=[tarea_consulta],
    verbose=True,
)


if __name__ == "__main__":
    print("Inicia primero el backend con: uvicorn app.main:app --reload --port 8000")
    print("Descomenta equipo.kickoff() para ejecutar la prueba con CrewAI.")
    resultado = equipo.kickoff()
    print(resultado)
