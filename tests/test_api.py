import os
import unittest
from unittest.mock import AsyncMock, Mock, patch

from bson import ObjectId
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pymongo.errors import ServerSelectionTimeoutError

from app.core.config import Settings
from app.core.database import connect_to_mongo
from app.main import app
from app.schemas.entidad import EntidadRespuesta
from app.schemas.traza import TrazaAgenteRespuesta
from app.services.entidad_service import entidad_service
from app.services.traza_service import traza_service


class SchemaTests(unittest.TestCase):
    def test_mongodb_url_is_required(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValidationError):
                Settings(_env_file=None)

    def test_object_ids_are_serialized_as_strings(self) -> None:
        object_id = ObjectId()
        entity = EntidadRespuesta.model_validate(
            {
                "_id": object_id,
                "id_referencia": "al_001",
                "nombre": "Daniel Vázquez",
                "tipo_entidad": "Alumno",
            }
        )
        trace = TrazaAgenteRespuesta.model_validate(
            {
                "_id": object_id,
                "session_id": "session-1",
                "agente_rol": "consultor",
                "entrada_query": "al_001",
                "respuesta_salida": "Encontrado",
            }
        )

        self.assertEqual(entity.id, str(object_id))
        self.assertEqual(trace.id, str(object_id))
        self.assertIsNotNone(trace.timestamp.tzinfo)


class DatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_unreachable_mongodb_has_actionable_error(self) -> None:
        client = Mock()
        client.admin.command = AsyncMock(
            side_effect=ServerSelectionTimeoutError("connection refused")
        )

        with patch("app.core.database.AsyncIOMotorClient", return_value=client):
            with self.assertRaisesRegex(
                RuntimeError,
                "Configura MONGODB_URL en .env",
            ):
                await connect_to_mongo()

        client.close.assert_called_once_with()


class ApiTests(unittest.TestCase):
    def test_entity_and_trace_routes(self) -> None:
        object_id = ObjectId()
        entity = {
            "_id": object_id,
            "id_referencia": "al_001",
            "nombre": "Daniel Vázquez",
            "tipo_entidad": "Alumno",
            "atributos": {"promedio": 9.1},
            "relaciones": {},
        }
        trace = {
            "_id": object_id,
            "session_id": "session-1",
            "agente_rol": "consultor",
            "entrada_query": "al_001",
            "respuesta_salida": "Encontrado",
        }

        with (
            patch("app.main.connect_to_mongo", new_callable=AsyncMock),
            patch("app.main.close_mongo_connection", new_callable=AsyncMock),
            TestClient(app) as client,
        ):
            with patch.object(
                entidad_service,
                "obtener_por_id_referencia",
                new=AsyncMock(return_value=entity),
            ):
                response = client.get("/api/v1/entidades/al_001")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["_id"], str(object_id))

            with patch.object(
                entidad_service,
                "obtener_por_id_referencia",
                new=AsyncMock(return_value=None),
            ):
                response = client.get("/api/v1/entidades/ausente")
            self.assertEqual(response.status_code, 404)

            with patch.object(
                entidad_service,
                "listar_por_tipo",
                new=AsyncMock(return_value=[entity]),
            ) as listar:
                response = client.get("/api/v1/entidades/?tipo=Alumno&limit=1")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()), 1)
            listar.assert_awaited_once_with("Alumno", limit=1)

            with patch.object(
                traza_service,
                "registrar_traza",
                new=AsyncMock(return_value=trace),
            ):
                response = client.post(
                    "/api/v1/trazas/",
                    json={
                        "session_id": "session-1",
                        "agente_rol": "consultor",
                        "entrada_query": "al_001",
                        "respuesta_salida": "Encontrado",
                    },
                )
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()["_id"], str(object_id))

            with patch.object(
                traza_service,
                "obtener_trazas_sesion",
                new=AsyncMock(return_value=[trace]),
            ) as obtener_trazas:
                response = client.get("/api/v1/trazas/sesion/session-1?limit=1")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()), 1)
            obtener_trazas.assert_awaited_once_with("session-1", limit=1)


if __name__ == "__main__":
    unittest.main()
