from typing import Any

from app.core.database import db
from app.schemas.entidad import EntidadCrear


class EntidadService:
    @property
    def collection(self):
        return db.get_collection("entidades")

    async def obtener_por_id_referencia(self, id_ref: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"id_referencia": id_ref})

    async def listar_por_tipo(
        self,
        tipo: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        cursor = self.collection.find({"tipo_entidad": tipo}).limit(limit)
        return await cursor.to_list(length=limit)

    async def crear_entidad(self, entidad: EntidadCrear) -> dict[str, Any]:
        document = entidad.model_dump()
        await self.collection.update_one(
            {"id_referencia": entidad.id_referencia},
            {"$set": document},
            upsert=True,
        )
        result = await self.obtener_por_id_referencia(entidad.id_referencia)
        if result is None:
            raise RuntimeError(
                f"MongoDB did not return entity '{entidad.id_referencia}' after upsert."
            )
        return result


entidad_service = EntidadService()
