from pydantic import BaseModel, Field
from typing import List

class Alumno(BaseModel):
    nombre: str
    apellidos: str
    matricula: str
    edad: int
    materias: List[str]

class Config:
    schema_extra = {
        "example" : {
            "nombre": "Daniel",
            "apellidos": "Vázquez",
            "matricula": "13345",
            "edad": 47,
            "materias": ["IA", "ML", "DM"]
        }
    }