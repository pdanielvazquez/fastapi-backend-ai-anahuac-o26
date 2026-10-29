from fastapi import APIRouter

from app.api.v1.endpoints import entidades, trazas

api_router = APIRouter()
api_router.include_router(
    entidades.router,
    prefix="/entidades",
    tags=["Entidades de Conocimiento"],
)
api_router.include_router(
    trazas.router,
    prefix="/trazas",
    tags=["Trazas de Agentes (Shapley)"],
)
