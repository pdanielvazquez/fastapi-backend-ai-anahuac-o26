import asyncio

import httpx
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool

API_BASE_URL = "http://localhost:8000/api/v1"
# API_BASE_URL = "http://localhost:8000/"

llm = LLM(
    model = "ollama/llama3.2",
    base_url = "http://localhost:11434",
)
print("Modelo funcionando correctamente")


# ==========================================
# CUSTOM TOOLS DE INTERACCIÓN CON FASTAPI
# ==========================================

@tool("Consultar Datos del Estudiante")
def consultar_estudiante_tool(estudiante_id: str) -> str:
    """Consulta la ficha informativa de un estudiante en MongoDB Atlas vía FastAPI."""
    try:
        response = httpx.get(f"{API_BASE_URL}/alumnos/{estudiante_id}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return f"Estudiante Encontrado: {data['nombre']} (Edad: {data['edad']}, Estatus: {data['estatus']}, IRI: {data['iri']})"
        return f"Error: No se encontró al estudiante {estudiante_id}."
    except Exception as e:
        return f"Error al conectar con la API: {str(e)}"


@tool("Consultar Datos de la Materia")
def consultar_materia_tool(materia_id: str) -> str:
    """Consulta los datos de una materia en MongoDB Atlas vía FastAPI."""
    try:
        response = httpx.get(f"{API_BASE_URL}/materias/{materia_id}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return f"Materia: {data['nombre_materia']} (Créditos: {data['creditos']}, IRI: {data['iri']})"
        return f"Error: No se encontró la materia {materia_id}."
    except Exception as e:
        return f"Error al conectar con la API: {str(e)}"


@tool("Validar Inscripción Semántica Ontológica")
def validar_semantica_tool(estudiante_id: str, materia_id: str, profesor_id: str) -> str:
    """Invoca la validación semántica efímera en FastAPI que ejecuta el razonador HermiT sobre la ontología OWL."""
    try:
        payload = {
            "estudiante_id": estudiante_id,
            "materia_id": materia_id,
            "profesor_id": profesor_id
        }
        response = httpx.post(f"{API_BASE_URL}/validar-semantica", json=payload, timeout=15)
        if response.status_code == 200:
            res = response.json()
            return (
                f"Dictamen Semántico: Valido={res['es_valido']} | "
                f"Mensaje: {res['mensaje']} | "
                f"Tiempo Razonador: {res['tiempo_razonamiento_ms']} ms | "
                f"Detalles: {', '.join(res['detalles_razonador'])}"
            )
        return f"Error en API Semántica: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Error de conexión con la API Semántica: {str(e)}"


# ==========================================
# DEFINICIÓN DE LOS 3 AGENTES
# ==========================================

agente_consultor = Agent(
    role="Agente Consultor Operativo de MongoDB",
    goal="Recuperar la información transaccional y de expediente de los alumnos, materias y profesores desde MongoDB Atlas.",
    backstory="Eres un especialista en bases de datos NoSQL encargado de extraer fichas informativas rápidas en milisegundos a través de endpoints REST.",
    tools=[consultar_estudiante_tool, consultar_materia_tool],
    verbose=True,
    llm=llm
)

agente_validador = Agent(
    role="Agente Validador Semántico OWL",
    goal="Evaluar si la solicitud de inscripción cumple estrictamente con las reglas lógicas y axiomas de la ontología OWL.",
    backstory="Eres un experto en Lógica Descriptiva y Razonadores Semánticos (HermiT). Tu trabajo es garantizar la consistencia lógica evitando violaciones de axiomas disjuntos o de cardinalidad.",
    tools=[validar_semantica_tool],
    verbose=True,
    llm=llm
)

agente_reporte = Agent(
    role="Agente Generador del Informe Final",
    goal="Sintetizar la información operativa obtenida de MongoDB Atlas con el dictamen lógico del razonador semántico para elaborar un reporte consolidado de inscripción.",
    backstory="Eres el coordinador del sistema multiagente. Integras las respuestas de los demás agentes y presentas un resumen ejecutivo claro y justificado.",
    tools=[],
    verbose=True,
    llm=llm
)


# ==========================================
# DEFINICIÓN DE TAREAS Y ORQUESTACIÓN
# ==========================================

async def ejecutar_sistema_multiagente(estudiante_id: str, materia_id: str, profesor_id: str):
    
    tarea_consulta = Task(
        description=f"Consultar los datos operativos del estudiante '{estudiante_id}' y de la materia '{materia_id}' utilizando las herramientas de MongoDB Atlas.",
        expected_output="Ficha operativa detallada del alumno y la materia.",
        agent=agente_consultor
    )

    tarea_validacion = Task(
        description=f"Ejecutar la validación semántica ontológica para la solicitud de inscripción del alumno '{estudiante_id}' en la materia '{materia_id}' impartida por el profesor '{profesor_id}'.",
        expected_output="Dictamen booleano de validez lógica y justificación del razonador HermiT.",
        agent=agente_validador
    )

    tarea_reporte = Task(
        description="Consolidar la ficha operativa del alumno/materia con el dictamen de validación semántica y generar un informe final de inscripción estructurado en Markdown.",
        expected_output="Informe final ejecutivo con el estado de la inscripción, datos del alumno, materia, profesor y justificación ontológica.",
        agent=agente_reporte
    )

    crew = Crew(
        agents=[agente_consultor, agente_validador, agente_reporte],
        tasks=[tarea_consulta, tarea_validacion, tarea_reporte],
        process=Process.sequential,
        verbose=True
    )

    resultado = await crew.kickoff_async()
    return resultado


if __name__ == "__main__":
    print("🚀 Iniciando prueba del Sistema Multiagente (CrewAI)...")
    res = asyncio.run(ejecutar_sistema_multiagente("al_001", "mat_001", "prof_001"))
    print("\n================ REPORT FINAL DEL MAS ================\n")
    print(res)
