# Guía Paso a Paso: Fase 2 - Escalado a Razonamiento Semántico Desacoplado (*Reasoning Offloading*) con FastAPI, Owlready2 y MongoDB Atlas

## 📌 Introducción y Objetivos de la Fase 2

En la **Fase 1** establecimos la infraestructura operativa base: un servicio asíncrono con **FastAPI** conectado a un clúster de **MongoDB Atlas**, permitiendo lecturas/escrituras masivas en milisegundos y el registro de trazas de ejecución de los agentes.

El objetivo de esta **Fase 2** es escalar la arquitectura hacia un sistema de **Base de Conocimientos Híbrida** mediante el patrón de **Descarga de Inferencia (*Reasoning Offloading*)**:

1. **Mantener MongoDB Atlas** como la fuente primaria de datos operativos, historiales y trazas transaccionales.
2. **Incorporar un Servicio Ontológico en FastAPI** utilizando **Owlready2** y el motor de razonamiento **HermiT**.
3. **Exponer Endpoints Semánticos Especializados** (`POST /api/v1/validar-semantica`) para evaluar restricciones lógicas complejas, clasificaciones implícitas y verificar la consistencia semántica bajo el Supuesto de Mundo Abierto (OWA) y axiomas de disyunción (`DisjointWith`).
4. **Actualizar Transparentemente las Custom Tools de CrewAI** sin reestructurar los agentes ni alterar el esquema de MongoDB Atlas.

---

## 🛠️ Requisitos Previos y Nuevas Dependencias

Para la ejecución de la Fase 2, se requiere contar con la instalación activa del entorno de la Fase 1 y agregar las dependencias de procesamiento ontológico y ejecución de Java (necesario para el motor HermiT de Owlready2).

### 1. Instalación de paquetes de Python
Ejecuta en tu entorno virtual:

```bash
pip install owlready2 rdflib
```

### 2. Verificación de Java JRE (Entorno de Ejecución del Razonador)
Owlready2 ejecuta internamente el razonador HermiT compilado en Java. Verifica que Java esté instalado en el sistema:

```bash
java -version
```

---

## 📂 Paso 1: Estructura del Proyecto Ampliada

Ampliamos el proyecto de FastAPI desarrollado en la Fase 1 agregando el módulo de servicios ontológicos y los esquemas de validación lógica:

```text
fastapi_mas_backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── api.py
│   │       └── endpoints/
│   │           ├── entidades.py
│   │           ├── trazas.py
│   │           └── validacion.py      # 👈 NUEVO: Endpoint semántico
│   ├── core/
│   │   ├── config.py
│   │   └── database.py
│   ├── ontology/
│   │   └── dominio_academico.owl      # 👈 NUEVO: Archivo de la ontología OWL
│   ├── schemas/
│   │   ├── entidad.py
│   │   ├── traza.py
│   │   └── validacion.py             # 👈 NUEVO: Esquemas Pydantic para validación
│   └── services/
│       ├── entidad_service.py
│       ├── traza_service.py
│       └── ontology_service.py        # 👈 NUEVO: Servicio de inferencia Owlready2
├── main.py
└── requirements.txt
```

---

## 🧱 Paso 2: Servicio Ontológico e Inferencia (`app/services/ontology_service.py`)

Este servicio se encarga de cargar la ontología OWL en memoria, instanciar afirmaciones temporales, invocar al razonador **HermiT** y verificar si existen inconsistencias lógicas o clasificaciones implícitas.

```python
import os
import logging
from typing import Dict, Any, List, Tuple
from owlready2 import get_ontology, sync_reasoner, OwlReadyInconsistentOntologyError, Nothing

logger = logging.getLogger("fastapi_mas")

class OntologyService:
    def __init__(self, owl_path: str):
        self.owl_path = owl_path
        self.onto = None
        self._cargar_ontologia()

    def _cargar_ontologia(self):
        """Carga el archivo OWL en el World de Owlready2."""
        if not os.path.exists(self.owl_path):
            logger.error(f"No se encontró el archivo de ontología en: {self.owl_path}")
            raise FileNotFoundError(f"Archivo OWL no encontrado en {self.owl_path}")
        
        try:
            self.onto = get_ontology(self.owl_path).load()
            logger.info(f"Ontología cargada exitosamente desde {self.owl_path}")
        except Exception as e:
            logger.error(f"Error al cargar la ontología: {str(e)}")
            raise e

    def validar_inscripcion_alumno(self, alumno_id: str, materia_id: str) -> Tuple[bool, str, List[str]]:
        """
        Valida si un alumno puede inscribirse a una materia específica evaluando
        las reglas semánticas y disyunciones en la ontología.
        """
        try:
            # 1. Buscar o crear instancias temporales en la ontología
            alumno = self.onto.search_one(iri=f"*{alumno_id}")
            materia = self.onto.search_one(iri=f"*{materia_id}")

            if not alumno:
                return False, f"El alumno '{alumno_id}' no existe en la base de conocimientos semántica.", []
            if not materia:
                return False, f"La materia '{materia_id}' no existe en la base de conocimientos semántica.", []

            # 2. Assert temporal de la relación
            alumno.estaInscritoEn.append(materia)

            # 3. Ejecutar el razonador HermiT
            inconsistencias = []
            es_valido = True
            mensaje = "Inscripción semánticamente válida."

            try:
                sync_reasoner(infer_property_values=True)
                
                # Verificar si el alumno fue inferido como Nothing (inconsistencia)
                if Nothing in alumno.is_a:
                    es_valido = False
                    mensaje = f"Inconsistencia Lógica: El alumno {alumno_id} viola restricciones de la materia {materia_id} (posible conflicto DisjointWith o falta de prerrequisitos)."
            except OwlReadyInconsistentOntologyError:
                es_valido = False
                mensaje = f"Error de Consistencia Ontológica: La inscripción de {alumno_id} en {materia_id} produce una contradicción semántica."

            # 4. Extraer inferencias derivadas
            materias_inferidas = [m.name for m in alumno.estaInscritoEn]

            # 5. Revertir el assert temporal para mantener limpia la ontología en memoria
            alumno.estaInscritoEn.remove(materia)

            return es_valido, mensaje, materias_inferidas

        except Exception as e:
            logger.error(f"Error durante el razonamiento semántico: {str(e)}")
            return False, f"Error interno en el motor de inferencia: {str(e)}", []

# Instancia global del servicio
OWL_FILE_PATH = os.path.join(os.path.dirname(__file__), "..", "ontology", "dominio_academico.owl")
ontology_service = OntologyService(owl_path=OWL_FILE_PATH)
```

---

## 📝 Paso 3: Esquemas Pydantic de Validación (`app/schemas/validacion.py`)

Definimos los modelos DTO para recibir las solicitudes de comprobación lógica emitidas por los agentes y entregar un dictamen estructurado.

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class ValidacionInscripcionRequest(BaseModel):
    alumno_id: str = Field(..., example="alumno_001", description="ID del individuo Alumno en la ontología")
    materia_id: str = Field(..., example="materia_001", description="ID del individuo Materia en la ontología")
    agente_solicitante: str = Field(..., example="AgenteValidadorReglas", description="Nombre del agente de CrewAI que solicita la validación")

class ValidacionSemanticaResponse(BaseModel):
    es_valido: bool = Field(..., description="Dictamen booleano de consistencia lógica")
    mensaje: str = Field(..., description="Explicación detallada del razonador")
    relaciones_inferidas: List[str] = Field(default=[], description="Relaciones lógicas derivadas tras la inferencia")
    tiempo_ejecucion_ms: float = Field(..., description="Tiempo consumido por el razonador HermiT")
```

---

## 🌐 Paso 4: Endpoint Semántico Especializado (`app/api/v1/endpoints/validacion.py`)

Creamos la ruta asíncrona en FastAPI que procesa la consulta con Owlready2 y automáticamente registra el resultado como una traza de auditoría en **MongoDB Atlas**.

```python
import time
from fastapi import APIRouter, HTTPException, status
from app.schemas.validacion import ValidacionInscripcionRequest, ValidacionSemanticaResponse
from app.schemas.traza import TrazaCrear
from app.services.ontology_service import ontology_service
from app.services.traza_service import TrazaService

router = APIRouter()

@router.post("/validar-inscripcion", response_model=ValidacionSemanticaResponse, status_code=status.HTTP_200_OK)
async def validar_inscripcion_semantica(solicitud: ValidacionInscripcionRequest):
    """
    Endpoint de Inferencia Semántica (Fase 2).
    Evalúa la consistencia de una inscripción utilizando el razonador HermiT
    y registra automáticamente el evento de auditoría en MongoDB Atlas.
    """
    inicio_tiempo = time.time()
    
    # 1. Ejecutar el razonamiento ontológico
    es_valido, mensaje, inferencias = ontology_service.validar_inscripcion_alumno(
        alumno_id=solicitud.alumno_id,
        materia_id=solicitud.materia_id
    )
    
    tiempo_total_ms = round((time.time() - inicio_tiempo) * 1000, 2)

    # 2. Registrar la traza del razonador en MongoDB Atlas (Persistencia Transaccional)
    traza_registro = TrazaCrear(
        agente_nombre=solicitud.agente_solicitante,
        accion="VALIDACION_ONTOLOGICA_INSCRIPCION",
        detalles={
            "alumno_id": solicitud.alumno_id,
            "materia_id": solicitud.materia_id,
            "dictamen_es_valido": es_valido,
            "mensaje_razonador": mensaje,
            "tiempo_razonamiento_ms": tiempo_total_ms
        },
        resultado_exito=es_valido
    )
    await TrazaService.registrar_traza(traza_registro)

    return ValidacionSemanticaResponse(
        es_valido=es_valido,
        mensaje=mensaje,
        relaciones_inferidas=inferencias,
        tiempo_ejecucion_ms=tiempo_total_ms
    )
```

Registramos el nuevo router en `app/api/v1/api.py`:

```python
from fastapi import APIRouter
from app.api.v1.endpoints import entidades, trazas, validacion

api_router = APIRouter()
api_router.include_router(entidades.router, prefix="/entidades", tags=["Entidades Operativas"])
api_router.include_router(trazas.router, prefix="/trazas", tags=["Trazas de Agentes"])
api_router.include_router(validacion.router, prefix="/validacion", tags=["Inferencia Semántica OWL"])
```

---

## 🤖 Paso 5: Custom Tool Refactorizada en CrewAI (`app/tools/crewai_tools.py`)

Esta es la pieza clave del **desacoplamiento**: los agentes en CrewAI continúan llamando a su `@tool` habitual, pero la herramienta ahora redirige la verificación lógica al endpoint semántico de FastAPI en lugar de procesar validaciones estáticas.

```python
import httpx
from crewai.tools import tool

FASTAPI_BASE_URL = "http://localhost:8000/api/v1"

@tool("Herramienta de Validación Semántica Ontológica")
def validar_inscripcion_materia_tool(alumno_id: str, materia_id: str) -> str:
    """
    Consulta al backend de FastAPI para validar semánticamente si un alumno
    puede inscribirse en una materia sin violar axiomas de la ontología OWL.
    
    Parámetros:
    - alumno_id: Identificador del alumno (ej. 'alumno_001')
    - materia_id: Identificador de la materia (ej. 'materia_001')
    """
    payload = {
        "alumno_id": alumno_id,
        "materia_id": materia_id,
        "agente_solicitante": "AgenteValidadorSemantico"
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(f"{FASTAPI_BASE_URL}/validacion/validar-inscripcion", json=payload)
            
            if response.status_code == 200:
                data = response.json()
                if data["es_valido"]:
                    return f"✅ VALIDADOR SEMÁNTICO: Inscripción autorizada. {data['mensaje']} (Tiempo: {data['tiempo_ejecucion_ms']} ms)"
                else:
                    return f"❌ VALIDADOR SEMÁNTICO: Inscripción rechazada. Motivo: {data['mensaje']} (Tiempo: {data['tiempo_ejecucion_ms']} ms)"
            else:
                return f"Error en el servidor FastAPI: Código {response.status_code} - {response.text}"

    except Exception as e:
        return f"Error de comunicación con el backend FastAPI: {str(e)}"
```

---

## 🧪 Paso 6: Verificación y Pruebas del Razonador

Podemos probar el funcionamiento del endpoint directamente utilizando `curl` o la interfaz interactiva Swagger (`http://localhost:8000/docs`).

### 1. Prueba de Caso Válido
```bash
curl -X 'POST' \
  'http://localhost:8000/api/v1/validacion/validar-inscripcion' \
  -H 'Content-Type: application/json' \
  -d '{
    "alumno_id": "alumno_001",
    "materia_id": "materia_001",
    "agente_solicitante": "AgenteValidadorSemantico"
  }'
```

**Respuesta Esperada:**
```json
{
  "es_valido": true,
  "mensaje": "Inscripción semánticamente válida.",
  "relaciones_inferidas": ["materia_001"],
  "tiempo_ejecucion_ms": 45.2
}
```

### 2. Verificación Automática en MongoDB Atlas
Tras ejecutar la prueba, puedes verificar en tu clúster de **MongoDB Atlas** dentro de la colección `trazas_agentes` que el evento fue registrado con sus métricas:

```json
{
  "_id": {"$oid": "6718d2..."},
  "agente_nombre": "AgenteValidadorSemantico",
  "accion": "VALIDACION_ONTOLOGICA_INSCRIPCION",
  "detalles": {
    "alumno_id": "alumno_001",
    "materia_id": "materia_001",
    "dictamen_es_valido": true,
    "mensaje_razonador": "Inscripción semánticamente válida.",
    "tiempo_razonamiento_ms": 45.2
  },
  "resultado_exito": true,
  "timestamp": "2026-10-29T16:15:00.000Z"
}
```

---

## 🎯 Conclusión del Escalado

Con esta **Fase 2** concluida:
* **MongoDB Atlas** gestiona la alta velocidad I/O y la persistencia de trazas para la auditoría de contribución (**Valores de Shapley**).
* **FastAPI** actúa como la fachada unificada de microservicios.
* **Owlready2 + HermiT** garantiza el rigor formal de la Lógica Descriptiva (OWL).
* **CrewAI** ejecuta agentes inteligentes capaces de consultar datos y validar reglas sin acoplar código rígido.
