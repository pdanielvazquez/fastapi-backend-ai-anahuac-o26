from fastapi import APIRouter, Body
from fastapi.encoders import jsonable_encoder
from database import collection
from models import Alumno

router = APIRouter()

@router.post("/", response_description="Agregando item a la colección de Alumnos")
async def setAlumno(item: Alumno = Body(...)):
    alumno = jsonable_encoder(item)
    nuevo = await collection.insert_one(alumno)
    return {"message": "Alumno agregado exitosamente"}

@router.get("/", response_description="Lista de alumnos de la colección")
async def getAlumnos():
    alumnos = []
    async for alumno in collection.find():
        if "_id" in alumno:
            alumno["_id"] = str(alumno["_id"])
        alumnos.append(alumno)
    return alumnos