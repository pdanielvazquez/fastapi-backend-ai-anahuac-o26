# Práctica Guiada: Implementación de una Base de Conocimientos Semántica Híbrida (TBox en OWL + ABox Efímero en FastAPI/MongoDB Atlas) e Integración con un Sistema Multiagente (CrewAI)

## 📌 Introducción y Enfoque Arquitectónico

En esta práctica guiada se implementará una **Base de Conocimientos Semántica Híbrida** utilizando el patrón de arquitectura desacoplada **TBox (Caja Terminológica) / ABox (Caja de Aserciones) Efímero**:

1. **TBox Estático (`ontologia-ia-anahuac-ejemplo-1.owl`):** Contiene la lógica del dominio, las clases (`Alumno`, `Profesor`, `Materia`), las subclases disjuntas (`DisjointClasses`), el dominio/rango de las propiedades (`ObjectProperty`, `DataProperty`) y los axiomas de cardinalidad. Permanece **inmutable en disco**.
2. **ABox Operativo (MongoDB Atlas):** Almacena de forma persistente y rápida los documentos BSON de alumnos, materias, profesores e historiales de inscripción.
3. **ABox Efímero en Memoria (RAM / Heap en FastAPI):** Durante la ejecución de peticiones HTTP de validación semántica, FastAPI recupera los datos crudos de MongoDB Atlas, instancia "al vuelo" (*on-the-fly*) únicamente a los individuos involucrados en la RAM de Python usando `owlready2`, asevera sus relaciones temporales y ejecuta el razonador **HermiT**. Al finalizar la inferencia, se devuelve el dictamen y las instancias se liberan de la memoria sin modificar el archivo `.owl` en disco.

---

## 🛠️ Requisitos Previos y Estructura del Proyecto

Asegúrate de contar con las siguientes librerías instaladas en tu entorno virtual de Python:

```bash
pip install fastapi uvicorn motor pydantic owlready2 httpx crewai
```

Estructura inicial del proyecto:

```text
proyecto_kdb_hibrido/
├── ontologia-ia-anahuac-ejemplo-1.owl   # Archivo OWL de la ontología
├── models.py                             # Esquemas y DTOs de Pydantic v2
├── main.py                               # API FastAPI + Motor + Servicio Ontológico
└── mas_crew.py                           # Sistema Multiagente con CrewAI (3 Agentes)
```

---

## 📝 Paso 1: Modelado de Datos y Esquemas Pydantic (`models.py`)

Comenzamos extendiendo el archivo `models.py` para definir los esquemas de validación de **Pydantic v2**, incluyendo la conversión de identificadores de MongoDB (`ObjectId`) a cadenas JSON y la generación del atributo `iri` (*Internationalized Resource Identifier*).

Crea o actualiza el archivo `models.py` con el siguiente código:

```python
from pydantic import BaseModel, Field, ConfigDict, GetCoreSchemaHandler
from pydantic_core import core_schema
from typing import List, Optional, Any
from datetime import datetime
from bson import ObjectId


class PyObjectId(str):
    """
    Adaptador de tipo personalizado para mapear los ObjectId de MongoDB (BSON)
    a cadenas de texto compatibles con JSON en Pydantic v2.
    """
    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, _handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(ObjectId),
                core_schema.str_schema(),
            ]),
            serialization=core_schema.plain_serializer_function_ser_schema(lambda x: str(x)),
        )


# ==========================================
# ESQUEMAS CRUD BASE
# ==========================================

class AlumnoBase(BaseModel):
    estudiante_id: str = Field(..., description="Matrícula única del alumno, ej. al_001")
    nombre: str = Field(..., description="Nombre completo del alumno")
    edad: int = Field(..., ge=15, le=100)
    genero: str = Field(..., description="masculino / femenino")
    peso: float = Field(..., description="Peso en kg")
    estatus: str = Field(default="Activo")
    clase_ontologica: str = Field(default="Alumno")


class AlumnoCreate(AlumnoBase):
    pass


class AlumnoResponse(AlumnoBase):
    id: PyObjectId = Field(alias="_id")
    iri: str = Field(..., description="IRI semántico unívoco dentro de la ontología")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )


class ProfesorBase(BaseModel):
    profesor_id: str = Field(..., description="Identificador único del profesor, ej. prof_001")
    nombre: str = Field(..., description="Nombre completo")
    categoria: str = Field(default="Titular")
    clase_ontologica: str = Field(default="Profesor")


class ProfesorCreate(ProfesorBase):
    pass


class ProfesorResponse(ProfesorBase):
    id: PyObjectId = Field(alias="_id")
    iri: str = Field(..., description="IRI semántico unívoco")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )


class MateriaBase(BaseModel):
    materia_id: str = Field(..., description="Clave de la materia, ej. mat_001")
    nombre_materia: str = Field(..., description="Nombre de la asignatura")
    creditos: int = Field(..., ge=1, le=20)
    clase_ontologica: str = Field(default="Materia")


class MateriaCreate(MateriaBase):
    pass


class MateriaResponse(MateriaBase):
    id: PyObjectId = Field(alias="_id")
    iri: str = Field(..., description="IRI semántico unívoco")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )


# ==========================================
# ESQUEMAS PARA VALIDACIÓN SEMÁNTICA HÍBRIDA
# ==========================================

class SolicitudInscripcion(BaseModel):
    estudiante_id: str = Field(..., description="Identificador del alumno")
    materia_id: str = Field(..., description="Identificador de la materia")
    profesor_id: str = Field(..., description="Identificador del profesor titular")


class ResultadoValidacionSemantica(BaseModel):
    es_valido: bool
    mensaje: str
    detalles_razonador: List[str] = []
    tiempo_razonamiento_ms: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TrazaAuditoria(BaseModel):
    solicitud: SolicitudInscripcion
    resultado: ResultadoValidacionSemantica
    agente_emisor: str = "Agente_Validador_Semantico"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

**Explicación de la tarea realizada:**
* Se implementó el adaptador `PyObjectId` para serializar los IDs nativos de MongoDB a JSON.
* Se estructuraron los modelos DTO de entrada y salida para `Alumno`, `Profesor` y `Materia`, agregando el campo `iri` que mapeará los registros de MongoDB con la ontología semántica.
* Se crearon las clases `SolicitudInscripcion`, `ResultadoValidacionSemantica` y `TrazaAuditoria` para gestionar el intercambio de datos con el razonador semántico y el log de auditoría.

---

## ⚡ Paso 2 y 3: Servidor FastAPI, CRUD y Servicio Ontológico Efímero (`main.py`)

A continuación, implementaremos el archivo `main.py`. Este archivo incluye:
1. Conexión asíncrona a **MongoDB Atlas** usando `Motor`.
2. Endpoints CRUD convencionales para registrar y consultar alumnos, materias y profesores.
3. El servicio ontológico `OntologyService` que carga la ontología en RAM y realiza instanciaciones efímeras en el Heap de Python para validar axiomas con **HermiT**.
4. El endpoint híbrido `POST /api/v1/validar-semantica`.

Escribe el siguiente código completo en `main.py`:

```python
import time
import os
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorClient
import owlready2 as owl

from models import (
    AlumnoCreate, AlumnoResponse,
    ProfesorCreate, ProfesorResponse,
    MateriaCreate, MateriaResponse,
    SolicitudInscripcion, ResultadoValidacionSemantica, TrazaAuditoria
)

# Configuración de Variables de Entorno y MongoDB Atlas
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "kdb_hibrida"
ONTOLOGY_PATH = "ontologia-ia-anahuac-ejemplo-1.owl"
BASE_IRI = "https://example.com/ontologia#"

# Clientes globales
mongo_client: AsyncIOMotorClient = None
db = None
ontologia = None


# ==========================================
# LIFESPAN DE FASTAPI (Inicialización y Cierre)
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global mongo_client, db, ontologia
    # 1. Inicializar conexión asíncrona con MongoDB Atlas
    mongo_client = AsyncIOMotorClient(MONGO_URI)
    db = mongo_client[DB_NAME]
    print("Conexión establecida con MongoDB Atlas.")

    # 2. Cargar el TBox de la ontología en RAM (Owlready2)
    if os.path.exists(ONTOLOGY_PATH):
        ontologia = owl.get_ontology(ONTOLOGY_PATH).load()
        print(f"TBox de Ontología cargado en memoria RAM desde {ONTOLOGY_PATH}.")
    else:
        print(f"Advertencia: No se encontró el archivo {ONTOLOGY_PATH}. El razonador funcionará en modo simulado.")

    yield

    # Cierre de conexiones
    mongo_client.close()
    print("Conexión con MongoDB Atlas cerrada.")


app = FastAPI(
    title="API de Base de Conocimiento Semántica Híbrida",
    version="2.0.0",
    description="Backend desacoplado: CRUD en MongoDB Atlas + ABox Efímero en RAM (Owlready2 + HermiT)",
    lifespan=lifespan
)


# ==========================================
# FUNCIONES AUXILIARES DE IRI
# ==========================================
def generar_iri(id_entidad: str) -> str:
    return f"{BASE_IRI}{id_entidad}"


# ==========================================
# ENDPOINTS CRUD BÁSICOS (Fase Operativa)
# ==========================================

@app.post("/api/v1/alumnos", response_model=AlumnoResponse, status_code=status.HTTP_201_CREATED)
async def crear_alumno(alumno: AlumnoCreate):
    existente = await db.alumnos.find_one({"estudiante_id": alumno.estudiante_id})
    if existente:
        raise HTTPException(status_code=400, detail="El estudiante ya existe en MongoDB Atlas.")
    
    doc = alumno.model_dump()
    doc["iri"] = generar_iri(alumno.estudiante_id)
    resultado = await db.alumnos.insert_one(doc)
    
    doc_creado = await db.alumnos.find_one({"_id": resultado.inserted_id})
    return doc_creado


@app.get("/api/v1/alumnos/{estudiante_id}", response_model=AlumnoResponse)
async def obtener_alumno(estudiante_id: str):
    doc = await db.alumnos.find_one({"estudiante_id": estudiante_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado en MongoDB Atlas.")
    return doc


@app.post("/api/v1/profesores", response_model=ProfesorResponse, status_code=status.HTTP_201_CREATED)
async def crear_profesor(profesor: ProfesorCreate):
    existente = await db.profesores.find_one({"profesor_id": profesor.profesor_id})
    if existente:
        raise HTTPException(status_code=400, detail="El profesor ya existe.")
    
    doc = profesor.model_dump()
    doc["iri"] = generar_iri(profesor.profesor_id)
    resultado = await db.profesores.insert_one(doc)
    return await db.profesores.find_one({"_id": resultado.inserted_id})


@app.get("/api/v1/profesores/{profesor_id}", response_model=ProfesorResponse)
async def obtener_profesor(profesor_id: str):
    doc = await db.profesores.find_one({"profesor_id": profesor_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Profesor no encontrado.")
    return doc


@app.post("/api/v1/materias", response_model=MateriaResponse, status_code=status.HTTP_201_CREATED)
async def crear_materia(materia: MateriaCreate):
    existente = await db.materias.find_one({"materia_id": materia.materia_id})
    if existente:
        raise HTTPException(status_code=400, detail="La materia ya existe.")
    
    doc = materia.model_dump()
    doc["iri"] = generar_iri(materia.materia_id)
    resultado = await db.materias.insert_one(doc)
    return await db.materias.find_one({"_id": resultado.inserted_id})


@app.get("/api/v1/materias/{materia_id}", response_model=MateriaResponse)
async def obtener_materia(materia_id: str):
    doc = await db.materias.find_one({"materia_id": materia_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Materia no encontrada.")
    return doc


# ==========================================
# SERVICIO ONTOLÓGICO Y ABOX EFÍMERO (RAM)
# ==========================================

def ejecutar_validacion_semantica_efimera(
    alumno_doc: dict, materia_doc: dict, profesor_doc: dict
) -> ResultadoValidacionSemantica:
    """
    Instancia 'on-the-fly' a los 3 individuos en el Heap de RAM usando Owlready2,
    asevera sus relaciones temporales, corre el razonador HermiT y destruye las
    instancias en memoria sin alterar el archivo .owl en disco.
    """
    inicio = time.time()
    detalles = []
    es_valido = True
    mensaje = "Validación semántica aprobada satisfactoriamente."

    if ontologia is None:
        return ResultadoValidacionSemantica(
            es_valido=True,
            mensaje="Validación en modo simulado (Ontología no cargada).",
            detalles_razonador=["Modo fallback activo"],
            tiempo_razonamiento_ms=round((time.time() - inicio) * 1000, 2)
        )

    try:
        with ontologia:
            # 1. Obtención de referencias a las clases del TBox
            ClaseAlumno = getattr(ontologia, alumno_doc.get("clase_ontologica", "Alumno"), None)
            ClaseMateria = getattr(ontologia, materia_doc.get("clase_ontologica", "Materia"), None)
            ClaseProfesor = getattr(ontologia, profesor_doc.get("clase_ontologica", "Profesor"), None)

            # 2. Instanciación Efímera en el Heap de RAM (ABox temporal)
            temp_alumno = ClaseAlumno(alumno_doc["estudiante_id"])
            temp_materia = ClaseMateria(materia_doc["materia_id"])
            temp_profesor = ClaseProfesor(profesor_doc["profesor_id"])

            # Aserción de propiedades de datos
            if hasattr(temp_alumno, "tieneEdad"):
                temp_alumno.tieneEdad = [alumno_doc.get("edad", 20)]

            # Aserción de propiedades de objetos (Relaciones)
            if hasattr(temp_profesor, "esProfesorTitularDe"):
                temp_profesor.esProfesorTitularDe.append(temp_materia)
            
            if hasattr(temp_alumno, "inscritoEn"):
                temp_alumno.inscritoEn.append(temp_materia)

            # 3. Validación de Axiomas de Disyunción (DisjointWith)
            if hasattr(ontologia, "Empleado") and issubclass(ClaseAlumno, getattr(ontologia, "Empleado")):
                es_valido = False
                mensaje = "Violación de Axioma: La entidad está clasificada bajo clases disjuntas (Alumno vs Empleado)."
                detalles.append("Inconsistencia en jerarquía de clases disjuntas.")

            # 4. Invocación del Razonador HermiT sobre el modelo en RAM
            if es_valido:
                try:
                    owl.sync_reasoner_hermit(infer_property_values=True)
                    detalles.append("Inferencia completada sin contradicciones lógicas.")
                except owl.OwlReadyInconsistentOntologyError:
                    es_valido = False
                    mensaje = "El razonador HermiT detectó inconsistencias semánticas en la ontología."
                    detalles.append("Error: Inconsistencia lógica tras aplicar axiomas.")

            # 5. Limpieza Efímera: Destruir instancias temporales en RAM
            owl.destroy_entity(temp_alumno)
            owl.destroy_entity(temp_materia)
            owl.destroy_entity(temp_profesor)

    except Exception as e:
        es_valido = False
        mensaje = f"Error durante el razonamiento semántico: {str(e)}"
        detalles.append(str(e))

    tiempo_total = round((time.time() - inicio) * 1000, 2)
    return ResultadoValidacionSemantica(
        es_valido=es_valido,
        mensaje=mensaje,
        detalles_razonador=detalles,
        tiempo_razonamiento_ms=tiempo_total
    )


# ==========================================
# ENDPOINT DE VALIDACIÓN SEMÁNTICA HÍBRIDA
# ==========================================

@app.post("/api/v1/validar-semantica", response_model=ResultadoValidacionSemantica)
async def validar_semantica_inscripcion(solicitud: SolicitudInscripcion):
    # 1. Recuperar los documentos operativos desde MongoDB Atlas
    alumno_doc = await db.alumnos.find_one({"estudiante_id": solicitud.estudiante_id})
    if not alumno_doc:
        raise HTTPException(status_code=404, detail=f"Alumno {solicitud.estudiante_id} no existe en MongoDB Atlas.")

    materia_doc = await db.materias.find_one({"materia_id": solicitud.materia_id})
    if not materia_doc:
        raise HTTPException(status_code=404, detail=f"Materia {solicitud.materia_id} no existe en MongoDB Atlas.")

    profesor_doc = await db.profesores.find_one({"profesor_id": solicitud.profesor_id})
    if not profesor_doc:
        raise HTTPException(status_code=404, detail=f"Profesor {solicitud.profesor_id} no existe en MongoDB Atlas.")

    # 2. Ejecutar la validación ontológica efímera en RAM
    resultado = ejecutar_validacion_semantica_efimera(alumno_doc, materia_doc, profesor_doc)

    # 3. Registrar la Traza de Auditoría en MongoDB Atlas
    traza = TrazaAuditoria(
        solicitud=solicitud,
        resultado=resultado,
        agente_emisor="Agente_Validador_Semantico"
    )
    await db.trazas.insert_one(traza.model_dump())

    return resultado

```

## 🤖 Paso 4: Construcción del Sistema Multiagente (`mas_crew.py`)

Ahora construizemos el Sistema Multiagente (MAS) utilizando **CrewAI**. El MAS estará compuesto por 3 agentes especializados:

1. **Agente Consultor Operativo (`Agente_Consultor`):** Consulta la información transaccional de alumnos, materias y profesores almacenada en MongoDB Atlas a través de los endpoints CRUD de FastAPI.
2. **Agente Validador Semántico (`Agente_Validador_Semantico`):** Invoca el endpoint semántico `POST /api/v1/validar-semantica` para verificar que la inscripción no viole axiomas ontológicos.
3. **Agente Generador de Reporte (`Agente_Reporte`):** Consolida los datos operativos y el dictamen lógico, generando un informe final estructurado.

Crea el archivo `mas_crew.py` con el siguiente código:

```python
import httpx
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool

API_BASE_URL = "http://localhost:8000/api/v1"


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
    verbose=True
)

agente_validador = Agent(
    role="Agente Validador Semántico OWL",
    goal="Evaluar si la solicitud de inscripción cumple estrictamente con las reglas lógicas y axiomas de la ontología OWL.",
    backstory="Eres un experto en Lógica Descriptiva y Razonadores Semánticos (HermiT). Tu trabajo es garantizar la consistencia lógica evitando violaciones de axiomas disjuntos o de cardinalidad.",
    tools=[validar_semantica_tool],
    verbose=True
)

agente_reporte = Agent(
    role="Agente Generador del Informe Final",
    goal="Sintetizar la información operativa obtenida de MongoDB Atlas con el dictamen lógico del razonador semántico para elaborar un reporte consolidado de inscripción.",
    backstory="Eres el coordinador del sistema multiagente. Integras las respuestas de los demás agentes y presentas un resumen ejecutivo claro y justificado.",
    tools=[],
    verbose=True
)


# ==========================================
# DEFINICIÓN DE TAREAS Y ORQUESTACIÓN
# ==========================================

def ejecutar_sistema_multiagente(estudiante_id: str, materia_id: str, profesor_id: str):
    
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

    resultado = crew.kickoff()
    return resultado


if __name__ == "__main__":
    print("🚀 Iniciando prueba del Sistema Multiagente (CrewAI)...")
    res = ejecutar_sistema_multiagente("al_001", "mat_001", "prof_001")
    print("\n================ REPORT FINAL DEL MAS ================\n")
    print(res)
```

**Explicación de la tarea realizada:**
* Se crearon herramientas personalizadas con `@tool` de CrewAI utilizando `httpx` para conectar a los agentes con los endpoints CRUD y semánticos de FastAPI.
* Se configuraron los tres agentes con roles bien diferenciados: *Agente Consultor* (lectura NoSQL rápida), *Agente Validador Semántico* (verificación ontológica con HermiT) y *Agente Generador de Reporte* (síntesis ejecutiva).
* Se orquestaron las tareas secuenciales en una `Crew` para obtener un reporte consolidado.

---

## 🧪 Paso 5: Verificación y Casos de Prueba

Sigue esta secuencia de pasos para verificar la solución completa:

### 1. Iniciar el Servidor Backend en FastAPI
En una terminal, ejecuta:

```bash
uvicorn main:app --reload --port 8000
```

### 2. Registrar Datos de Prueba en MongoDB Atlas (Vía HTTP/JSON en Swagger UI `http://localhost:8000/docs`)

O bien mediante peticiones cliente en Python:

```python
import httpx

httpx.post("http://localhost:8000/api/v1/alumnos", json={
    "estudiante_id": "al_001", "nombre": "Daniel Vázquez", "edad": 22, "genero": "masculino", "peso": 70.5
})
httpx.post("http://localhost:8000/api/v1/profesores", json={
    "profesor_id": "prof_001", "nombre": "Dra. Elena Ríos", "categoria": "Titular"
})
httpx.post("http://localhost:8000/api/v1/materias", json={
    "materia_id": "mat_001", "nombre_materia": "Agentes Inteligentes", "creditos": 8
})
```

### 3. Ejecutar el Sistema Multiagente (CrewAI)

En otra terminal, ejecuta el script agéntico:

```bash
python mas_crew.py
```

### 📊 Resultado Esperado en el Reporte del MAS

El *Agente Generador de Reporte* emitirá un resultado similar a:

```markdown
# Informe de Solicitud de Inscripción Híbrida

## 1. Datos Operativos (MongoDB Atlas)
* **Alumno:** Daniel Vázquez (`al_001`) | Edad: 22 | Estatus: Activo
* **Materia:** Agentes Inteligentes (`mat_001`) | Créditos: 8
* **IRI Semántico Asignado:** https://example.com/ontologia#al_001

## 2. Dictamen de Validación Semántica (Ontología OWL + HermiT)
* **Estado:** ✅ APROBADO (Válido: True)
* **Mensaje:** Validación semántica aprobada satisfactoriamente.
* **Tiempo de Inferencia en RAM:** 14.2 ms
* **Axiomas Evaluados:** Jerarquía de Clases (`Alumno`), Propiedades de Objetos (`inscritoEn`, `esProfesorTitularDe`) y ausencia de contradicciones por subclases disjuntas.

## 3. Conclusión del Sistema Multiagente
La inscripción es completamente consistente tanto a nivel operativo (documento activo en MongoDB Atlas) como a nivel semántico (axiomas validados en RAM por el razonador HermiT). Se ha guardado la traza de auditoría correspondiente.
```

---

## 📌 Conclusiones de la Práctica

1. **Separación TBox / ABox Efímero:** Se demostró cómo mantener inmutable el archivo `.owl` en disco permite evaluar reglas lógicas en milisegundos sin sobrecargar el motor de razonamiento.
2. **Escalabilidad Operativa:** MongoDB Atlas gestiona los datos transaccionales masivos, mientras que FastAPI une temporalmente ambos mundos en el *Heap* de Python.
3. **Desacoplamiento Agéntico:** Los agentes en CrewAI consumen servicios REST transparentes, delegando la complejidad del razonamiento ontológico y la persistencia NoSQL al backend de FastAPI.
