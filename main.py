from fastapi import FastAPI
from routes.alumno import router as AlumnoRouter

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}

# Agregando las rutas del alumno0
app.include_router(AlumnoRouter, prefix="/alumnos")