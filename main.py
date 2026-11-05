import time
import os
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorClient
import owlready2 as owl
from owlready2 import reasoning

reasoning.JAVA_MEMORY = 1024  # MB; probar un valor menor si no logra reservarlo

from models import (
    AlumnoCreate, AlumnoResponse,
    ProfesorCreate, ProfesorResponse,
    MateriaCreate, MateriaResponse,
    SolicitudInscripcion, ResultadoValidacionSemantica, TrazaAuditoria
)

# Configuración de Variables de Entorno y MongoDB Atlas
MONGO_URI = os.getenv("MONGO_URL", "mongodb+srv://pdanielvazquez_db_user:eMSYb7iAzx0MYpaK@cluster0.54drn85.mongodb.net/")
DB_NAME = "kdb_hibrida"
ONTOLOGY_PATH = "ontologia-ia-anahuac-ejemplo-1.owx"
BASE_IRI = "http://www.semanticweb.org/pdani/ontologies/2026/7/ontologia-ia-anahuac#"

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
