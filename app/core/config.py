from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "MAS Knowledge Base API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    MONGODB_URL: str = Field(min_length=1)
    DATABASE_NAME: str = "mas_knowledge_db"
    ONTOLOGY_PATH: Path = (
        Path(__file__).resolve().parents[2] / "ontologia-ia-anahuac-ejemplo-1.owx"
    )
    REASONER_JAVA_MEMORY_MB: int = Field(default=512, ge=256)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
