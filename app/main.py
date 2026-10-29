from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import close_mongo_connection, connect_to_mongo


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    await connect_to_mongo()
    try:
        yield
    finally:
        await close_mongo_connection()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Backend de persistencia operativa para sistemas multiagente "
        "con CrewAI y MongoDB."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Health Check"])
async def root() -> dict[str, str]:
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }
