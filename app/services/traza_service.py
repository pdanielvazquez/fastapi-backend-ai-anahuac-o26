from datetime import datetime, timezone
from typing import Any

from app.core.database import db
from app.schemas.traza import TrazaAgenteCrear


class TrazaService:
    @property
    def collection(self):
        return db.get_collection("trazas_ejecucion")

    async def registrar_traza(self, traza: TrazaAgenteCrear) -> dict[str, Any]:
        document = traza.model_dump()
        document["timestamp"] = datetime.now(timezone.utc)
        result = await self.collection.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    async def obtener_trazas_sesion(
        self,
        session_id: str,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        cursor = (
            self.collection.find({"session_id": session_id})
            .sort("timestamp", 1)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)


traza_service = TrazaService()
