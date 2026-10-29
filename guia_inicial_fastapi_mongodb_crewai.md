# Guía de Implementación: Esqueleto Inicial en FastAPI + MongoDB Atlas con Pydantic y Motor (Fase 1)

**Asignatura:** Agentes Inteligentes (LIIS1213)  
**Institución:** Universidad Iberoamericana Puebla  
**Tema:** Infraestructura Backend para la Persistencia Operativa y Trazas de Sistemas Multiagente (CrewAI)

---

## 🎯 Contexto y Objetivos de la Fase 1

Esta guía detalla paso a paso la construcción de la **Capa Backend Base (Fase 1)** utilizando **FastAPI**, **Motor** (cliente asíncrono oficial de MongoDB en Python), **Pydantic v2** y una instancia administrada en la nube con **MongoDB Atlas**.

El propósito de esta fase es proporcionar a la enjambre de agentes de **CrewAI** una interfaz HTTP asíncrona de alto rendimiento que permita:
1. **Consultas Operativas Ultrarrápidas:** Recuperar datos de entidades, catálogos e historiales en milisegundos sin bloquear la ejecución de los modelos de lenguaje.
2. **Registro de Trazas (*Execution Logs*):** Almacenar los pensamientos, herramientas invocadas y respuestas de cada agente para alimentar posteriormente la capa de transparencia (**Valores de Shapley**).
3. **Escalabilidad Transparente:** Dejar lista la arquitectura para que en la **Fase 2** se incorpore el servidor de inferencia ontológica (OWL / Lógica Descriptiva) sin romper los contratos de la API ni reescribir los agentes.

---

## 📁 1. Estructura del Proyecto

Organizaremos el código siguiendo una **arquitectura modular limpia** en Python:

```text
fastapi_mas_backend/
├── app/
│   ├── __init__.py
│   ├── main.py                   # Punto de entrada de FastAPI y Lifespan
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py             # Configuración de variables de entorno (Pydantic Settings)
│   │   └── database.py           # Conexión asíncrona a MongoDB Atlas con Motor
│   ├── models/                   # Definición de entidades internas de MongoDB
│   │   └── __init__.py
│   ├── schemas/                  # Validadores Pydantic (DTOs para API y CrewAI)
│   │   ├── __init__.py
│   │   ├── entidad.py            # Esquema de datos del dominio
│   │   └── traza.py              # Esquema para auditoría de agentes
│   ├── api/
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py         # Enrutador principal de la v1
│   │       ├── endpoints/
│   │       │   ├── entidades.py  # Endpoints de consulta operativa
│   │       │   └── trazas.py     # Endpoints de registro de ejecuciones
│   ├── services/                 # Capa de lógica de negocio y DAO de MongoDB
│   │   ├── __init__.py
│   │   ├── entidad_service.py
│   │   └── traza_service.py
├── client_crewai_example.py      # Ejemplo de Custom Tool consumiendo la API desde CrewAI
├── .env                          # Archivo de variables de entorno (URI Atlas)
├── .gitignore
└── requirements.txt              # Dependencias del proyecto
```

---

## 🛠️ 2. Paso a Paso de la Implementación

### Paso 1: Configurar el Entorno y Dependencias (`requirements.txt` y `.env`)

Primero definimos las dependencias necesarias. Nota que utilizamos **Motor** para I/O asíncrono no bloqueante y **Pydantic v2** para la validación tipada.

#### `requirements.txt`
```text
fastapi>=0.110.0
uvicorn[standard]>=0.28.0
motor>=3.3.2
pydantic>=2.6.0
pydantic-settings>=2.2.0
python-dotenv>=1.0.1
httpx>=0.27.0
```

#### `.env`
Crea el archivo `.env` en la raíz sustituyendo `<usuario>`, `<password>` y `<cluster-url>` con tus credenciales de **MongoDB Atlas**:

```env
PROJECT_NAME="MAS Knowledge Base API"
VERSION="1.0.0"
API_V1_STR="/api/v1"

# URI de Conexión a MongoDB Atlas
MONGODB_URL="mongodb+srv://<usuario>:<password>@<cluster-url>.mongodb.net/?retryWrites=true&w=majority&appName=ClusterMAS"
DATABASE_NAME="mas_knowledge_db"
```

> **🔒 Nota de Seguridad:** Asegúrate de agregar `.env` a tu `.gitignore` para no exponer las credenciales de tu cluster de MongoDB Atlas en repositorios públicos.

---

### Paso 2: Módulo de Configuración (`app/core/config.py`)

Utilizamos `pydantic-settings` para cargar y validar las variables de entorno de forma fuertemente tipada.

```python
# app/core/config.py
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "MAS Knowledge Base API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Configuración MongoDB Atlas
    MONGODB_URL: str
    DATABASE_NAME: str = "mas_knowledge_db"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
```

---

### Paso 3: Conexión Asíncrona a MongoDB Atlas (`app/core/database.py`)

Motor utiliza el bucle de eventos (*event loop*) de `asyncio` de Python. Manejaremos la apertura y cierre de conexiones mediante el gestor de ciclo de vida (`lifespan`) de FastAPI.

```python
# app/core/database.py
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

logger = logging.getLogger("uvicorn")


class Database:
    client: AsyncIOMotorClient = None
    db = None


db = Database()


async def connect_to_mongo():
    """Establece la conexión asíncrona con el cluster de MongoDB Atlas."""
    logger.info("Conectando a MongoDB Atlas...")
    db.client = AsyncIOMotorClient(
        settings.MONGODB_URL,
        maxPoolSize=10,
        minPoolSize=1,
        serverSelectionTimeoutMS=5000,
    )
    db.db = db.client[settings.DATABASE_NAME]

    # Verificar conectividad con un ping
    try:
        await db.client.admin.command("ping")
        logger.info(
            f"✅ Conexión exitosa a MongoDB Atlas (BD: '{settings.DATABASE_NAME}')."
        )
    except Exception as e:
        logger.error(f"❌ Error al conectar a MongoDB Atlas: {e}")
        raise e


async def close_mongo_connection():
    """Cierra el pool de conexiones con MongoDB Atlas."""
    if db.client:
        logger.info("Cerrando conexión con MongoDB Atlas...")
        db.client.close()
        logger.info("🔒 Conexión con MongoDB Atlas cerrada.")
```

---

### Paso 4: Esquemas Pydantic para MongoDB (`app/schemas/`)

En Pydantic v2, el manejo de campos `_id` de BSON requiere una ligera adaptación para mapear de forma transparente entre las cadenas de texto JSON de la API y los objetos `ObjectId` de MongoDB.

#### A) Manejador de ObjectId y Esquema de Entidad (`app/schemas/entidad.py`)

```python
# app/schemas/entidad.py
from typing import Annotated, Any, Dict, List, Optional
from pydantic import BaseModel, BeforeValidator, Field

# Validador para convertir PyObjectId de BSON a string en JSON
PyObjectId = Annotated[str, BeforeValidator(str)]


class EntidadBase(BaseModel):
    id_referencia: str = Field(
        ..., description="Identificador de dominio (ej. al_001, mat_101)"
    )
    nombre: str = Field(..., description="Nombre o etiqueta principal")
    tipo_entidad: str = Field(
        ..., description="Categoría (ej. Alumno, Materia, Mueble)"
    )
    atributos: Dict[str, Any] = Field(
        default_factory=dict, description="Atributos de datos dinámicos"
    )
    relaciones: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Relaciones con otras entidades de la KB",
    )


class EntidadCrear(EntidadBase):
    pass


class EntidadRespuesta(EntidadBase):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id_referencia": "al_001",
                "nombre": "Daniel Vázquez",
                "tipo_entidad": "Alumno",
                "atributos": {"edad": 22, "promedio": 9.1},
                "relaciones": {"estaInscritoEn": ["mat_001", "mat_002"]},
            }
        }
```

#### B) Esquema para Registro de Trazas de Agentes (`app/schemas/traza.py`)

Este esquema guardará la ejecución de los agentes de **CrewAI** para respaldar el cálculo de los **Valores de Shapley**.

```python
# app/schemas/traza.py
from datetime import datetime
from typing import Annotated, Any, Dict, Optional
from pydantic import BaseModel, BeforeValidator, Field

PyObjectId = Annotated[str, BeforeValidator(str)]


class TrazaAgenteCrear(BaseModel):
    session_id: str = Field(
        ..., description="ID único del flujo de trabajo de la Crew"
    )
    agente_rol: str = Field(
        ..., description="Rol del agente en CrewAI (ej. Agente_Validador)"
    )
    herramienta_usada: Optional[str] = Field(
        None, description="Nombre de la @tool invocada"
    )
    entrada_query: str = Field(..., description="Prompt o parámetro de entrada")
    respuesta_salida: str = Field(
        ..., description="Resultado obtenido o decisión tomada"
    )
    exito: bool = Field(
        True, description="Indica si la acción se ejecutó sin errores"
    )
    metadatos: Dict[str, Any] = Field(
        default_factory=dict, description="Métricas de tiempo o uso de tokens"
    )


class TrazaAgenteRespuesta(TrazaAgenteCrear):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
```

---

### Paso 5: Capa de Servicios y Consultas a MongoDB (`app/services/`)

Aislamos las operaciones de la base de datos dentro de clases de servicio.

#### `app/services/entidad_service.py`
```python
# app/services/entidad_service.py
from typing import List, Optional
from app.core.database import db
from app.schemas.entidad import EntidadCrear


class EntidadService:

    @property
    def collection(self):
        return db.db["entidades"]

    async def obtener_por_id_referencia(
        self, id_ref: str
    ) -> Optional[dict]:
        """Busca una entidad por su ID de dominio (ej. 'al_001')."""
        return await self.collection.find_one({"id_referencia": id_ref})

    async def listar_por_tipo(
        self, tipo: str, limit: int = 50
    ) -> List[dict]:
        """Lista entidades filtradas por su tipo/clase."""
        cursor = self.collection.find({"tipo_entidad": tipo}).limit(limit)
        return await cursor.to_list(length=limit)

    async def crear_entidad(self, entidad: EntidadCrear) -> dict:
        """Inserta o actualiza una entidad en la colección."""
        doc = entidad.model_dump()
        await self.collection.update_one(
            {"id_referencia": entidad.id_referencia},
            {"$set": doc},
            upsert=True,
        )
        return await self.obtener_por_id_referencia(entidad.id_referencia)


entidad_service = EntidadService()
```

#### `app/services/traza_service.py`
```python
# app/services/traza_service.py
from typing import List
from app.core.database import db
from app.schemas.traza import TrazaAgenteCrear


class TrazaService:

    @property
    def collection(self):
        return db.db["trazas_ejecucion"]

    async def registrar_traza(self, traza: TrazaAgenteCrear) -> dict:
        """Guarda un evento de ejecución de un agente de CrewAI."""
        doc = traza.model_dump()
        doc["timestamp"] = doc.get("timestamp") or datetime.utcnow()
        result = await self.collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    async def obtener_trazas_sesion(self, session_id: str) -> List[dict]:
        """Recupera todas las trazas de una sesión para calcular Shapley."""
        cursor = self.collection.find({"session_id": session_id}).sort(
            "timestamp", 1
        )
        return await cursor.to_list(length=500)


traza_service = TrazaService()
```

---

### Paso 6: Endpoints de la API REST (`app/api/v1/endpoints/`)

Construimos las rutas REST que consumirán las herramientas de CrewAI.

#### A) Endpoints de Entidades (`app/api/v1/endpoints/entidades.py`)

```python
# app/api/v1/endpoints/entidades.py
from typing import List
from fastapi import APIRouter, HTTPException, Query, status
from app.schemas.entidad import EntidadCrear, EntidadRespuesta
from app.services.entidad_service import entidad_service

router = APIRouter()


@router.get(
    "/{id_referencia}",
    response_model=EntidadRespuesta,
    status_code=status.HTTP_200_OK,
)
async def obtener_entidad(id_referencia: str):
    """Endpoint de lectura rápida para el Agente Consultor."""
    entidad = await entidad_service.obtener_por_id_referencia(id_referencia)
    if not entidad:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"La entidad '{id_referencia}' no existe en la base de conocimientos.",
        )
    return entidad


@router.get(
    "/", response_model=List[EntidadRespuesta], status_code=status.HTTP_200_OK
)
async def listar_entidades_por_tipo(tipo: str = Query(..., example="Alumno")):
    """Lista entidades pertenecientes a una clase dada."""
    return await entidad_service.listar_por_tipo(tipo)


@router.post(
    "/",
    response_model=EntidadRespuesta,
    status_code=status.HTTP_201_CREATED,
)
async def guardar_entidad(entidad: EntidadCrear):
    """Crea o actualiza un registro en MongoDB Atlas."""
    return await entidad_service.crear_entidad(entidad)
```

#### B) Endpoints de Trazas (`app/api/v1/endpoints/trazas.py`)

```python
# app/api/v1/endpoints/trazas.py
from typing import List
from fastapi import APIRouter, status
from app.schemas.traza import TrazaAgenteCrear, TrazaAgenteRespuesta
from app.services.traza_service import traza_service

router = APIRouter()


@router.post(
    "/",
    response_model=TrazaAgenteRespuesta,
    status_code=status.HTTP_201_CREATED,
)
async def registrar_evento_agente(traza: TrazaAgenteCrear):
    """Registra la acción/herramienta de un agente para auditoría de Shapley."""
    return await traza_service.registrar_traza(traza)


@router.get(
    "/sesion/{session_id}",
    response_model=List[TrazaAgenteRespuesta],
    status_code=status.HTTP_200_OK,
)
async def obtener_trazas_por_sesion(session_id: str):
    """Recupera la secuencia de ejecuciones para el cálculo del valor de contribución."""
    return await traza_service.obtener_trazas_sesion(session_id)
```

#### C) Configurar el Router Principal (`app/api/v1/router.py`)

```python
# app/api/v1/router.py
from fastapi import APIRouter
from app.api.v1.endpoints import entidades, trazas

api_router = APIRouter()
api_router.include_router(
    entidades.router, prefix="/entidades", tags=["Entidades de Conocimiento"]
)
api_router.include_router(
    trazas.router, prefix="/trazas", tags=["Trazas de Agentes (Shapley)"]
)
```

---

### Paso 7: Servidor Principal y Lifecycle (`app/main.py`)

Configuramos el ciclo de vida asíncrono (`lifespan`) en FastAPI para garantizar la gestión correcta del pool de conexiones a MongoDB Atlas.

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import close_mongo_connection, connect_to_mongo


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Evento de inicio: Conectar a MongoDB Atlas
    await connect_to_mongo()
    yield
    # Evento de cierre: Cerrar conexiones
    await close_mongo_connection()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend de Persistencia Operativa para Sistema Multiagente con CrewAI y MongoDB Atlas",
    lifespan=lifespan,
)

# Permitir CORS para consultas desde agentes local/remoto
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir rutas de la API v1
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Health Check"])
async def root():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }
```

---

## 🤖 3. Integración con CrewAI (Consumo mediante `@tool`)

A continuación se muestra un ejemplo práctico en Python de cómo un **agente de CrewAI** consume esta API mediante el decorador `@tool` usando la librería asíncrona/síncrona `httpx`:

```python
# client_crewai_example.py
import httpx
from crewai import Agent, Crew, Task
from crewai.tools import tool

API_BASE_URL = "http://localhost:8000/api/v1"


# 1. Definición de la Custom Tool para CrewAI
@tool("Consulta de Base de Datos Operativa")
def consultar_entidad_kb_tool(id_referencia: str) -> str:
    """Consulta la base de conocimientos en MongoDB Atlas a través de FastAPI.

    Recibe el identificador único de la entidad (ej. 'al_001', 'mat_101').
    """
    try:
        response = httpx.get(
            f"{API_BASE_URL}/entidades/{id_referencia}", timeout=5.0
        )
        if response.status_code == 200:
            data = response.json()
            # Registrar traza de ejecución en la API de manera automática
            httpx.post(
                f"{API_BASE_URL}/trazas/",
                json={
                    "session_id": "sesion_demo_001",
                    "agente_rol": "Agente_Consultor_KB",
                    "herramienta_usada": "consultar_entidad_kb_tool",
                    "entrada_query": id_referencia,
                    "respuesta_salida": f"Entidad {data['nombre']} recuperada.",
                    "exito": True,
                },
            )
            return f"Datos encontrados: {data['nombre']} | Tipo: {data['tipo_entidad']} | Atributos: {data['atributos']}"
        elif response.status_code == 404:
            return f"La entidad '{id_referencia}' no existe en MongoDB Atlas."
        else:
            return f"Error en la API: {response.status_code}"
    except Exception as e:
        return f"Error de conexión con el backend FastAPI: {str(e)}"


# 2. Agente de CrewAI
agente_consultor = Agent(
    role="Agente Consultor de Base de Datos",
    goal="Recuperar información verídica de estudiantes y materias desde MongoDB Atlas.",
    backstory="Eres un especialista en extracción de datos operativos conectado a la API de FastAPI.",
    tools=[consultar_entidad_kb_tool],
    verbose=True,
)

# 3. Tarea
tarea_consulta = Task(
    description="Consulta la información del alumno registrado con ID 'al_001' y resume sus datos.",
    expected_output="Resumen claro con el nombre del alumno y sus atributos.",
    agent=agente_consultor,
)

# 4. Crew
equipo = Crew(
    agents=[agente_consultor], tasks=[tarea_consulta], verbose=True
)

if __name__ == "__main__":
    print("=== Ejecutando Prueba de Concepto CrewAI + FastAPI + Atlas ===")
    # Nota: Asegúrate de tener el servidor FastAPI corriendo en localhost:8000
    # resultado = equipo.kickoff()
    # print(resultado)
```

---

## 🧪 4. Despliegue y Pruebas de la Fase 1

### 1. Iniciar el Servidor FastAPI
Ejecuta el servidor en modo desarrollo utilizando Uvicorn:

```bash
uvicorn app.main:app --reload --port 8000
```

### 2. Verificar la Documentación Interactiva (Swagger UI)
Abre tu navegador e ingresa a: **`http://localhost:8000/docs`**.

Ahí podrás probar interactivamente:
* `POST /api/v1/entidades/`: Poblar datos de prueba en MongoDB Atlas.
* `GET /api/v1/entidades/al_001`: Verificar la consulta de lectura.
* `GET /api/v1/trazas/sesion/sesion_demo_001`: Revisar los eventos registrados para la auditoría de Shapley.

---

## 🔄 5. Hoja de Ruta para la Transición a la Fase 2

Cuando esta Fase 1 esté estable, la transición a la **Inferencia en Dos Fases** se realizará de la siguiente manera:

1. **Crear endpoint semántico en FastAPI (`POST /api/v1/validar-semantica`):** Se integrará `owlready2` en FastAPI para cargar la ontología `.owl` y ejecutar el razonador **HermiT**.
2. **Crear Tool del Validador en CrewAI:** Se agregará una herramienta `@tool` para el *Agente Validador* que llamará al nuevo endpoint semántico.
3. **Cero impacto en la DB:** MongoDB Atlas continuará siendo el almacén primario de lectura/escritura rápida, mientras que el motor ontológico solo procesará las reglas lógicas bajo demanda.
