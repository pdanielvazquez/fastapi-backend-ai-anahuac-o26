import logging

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)
from pymongo.errors import ServerSelectionTimeoutError

from app.core.config import settings

logger = logging.getLogger(__name__)


class Database:
    def __init__(self) -> None:
        self.client: AsyncIOMotorClient | None = None
        self.db: AsyncIOMotorDatabase | None = None

    def get_collection(self, name: str) -> AsyncIOMotorCollection:
        if self.db is None:
            raise RuntimeError("MongoDB is not connected.")
        return self.db[name]


db = Database()


async def connect_to_mongo() -> None:
    logger.info("Connecting to MongoDB...")
    client = AsyncIOMotorClient(
        settings.MONGODB_URL,
        maxPoolSize=10,
        minPoolSize=1,
        serverSelectionTimeoutMS=5000,
        tz_aware=True,
    )
    try:
        await client.admin.command("ping")
        database = client[settings.DATABASE_NAME]
        await database["entidades"].create_index(
            "id_referencia",
            unique=True,
            name="uq_entidades_id_referencia",
        )
        await database["trazas_ejecucion"].create_index(
            [("session_id", 1), ("timestamp", 1)],
            name="ix_trazas_session_timestamp",
        )
    except ServerSelectionTimeoutError as exc:
        client.close()
        logger.exception(
            "MongoDB is unreachable. Check MONGODB_URL and make sure the "
            "MongoDB service is running and accessible."
        )
        raise RuntimeError(
            "No se pudo conectar con MongoDB. Configura MONGODB_URL en .env "
            "con la URI de MongoDB Atlas o inicia MongoDB local."
        ) from exc
    except Exception:
        client.close()
        logger.exception("Could not connect to or initialize MongoDB.")
        raise

    db.client = client
    db.db = database
    logger.info("Connected to MongoDB database '%s'.", settings.DATABASE_NAME)


async def close_mongo_connection() -> None:
    if db.client is not None:
        logger.info("Closing MongoDB connection...")
        db.client.close()
        db.client = None
        db.db = None
        logger.info("MongoDB connection closed.")
