from crewai import Agent, Crew, Task, LLM

from app.tools.crewai_tools import (
    consultar_entidad_kb_tool,
    validar_inscripcion_materia_tool,
)


llm = LLM(
    model = "ollama/llama3.2",
    base_url = "http://localhost:11434",
)

agente_consultor = Agent(
    role="Agente Consultor de Base de Datos",
    goal="Recuperar información verídica desde la base operativa.",
    backstory="Especialista en consulta de datos mediante la API FastAPI.",
    tools=[consultar_entidad_kb_tool, validar_inscripcion_materia_tool],
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
