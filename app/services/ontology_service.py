import logging
from pathlib import Path
from threading import RLock

import owlready2.reasoning
from owlready2 import Nothing, World
from owlready2.base import OwlReadyInconsistentOntologyError

from app.core.config import settings


logger = logging.getLogger(__name__)


class OntologyService:
    def __init__(self, owl_path: Path, java_memory_mb: int = 512) -> None:
        self.owl_path = Path(owl_path).resolve()
        self._lock = RLock()
        if not self.owl_path.is_file():
            raise FileNotFoundError(
                f"No se encontró el archivo de ontología en: {self.owl_path}"
            )

        owlready2.reasoning.JAVA_MEMORY = java_memory_mb
        world, _ = self._load_ontology()
        world.close()
        logger.info("Ontología cargada desde %s", self.owl_path)

    def _load_ontology(self):
        world = World()
        try:
            ontology = world.get_ontology(str(self.owl_path)).load()
        except Exception:
            world.close()
            raise
        return world, ontology

    def validar_inscripcion_alumno(
        self,
        alumno_id: str,
        materia_id: str,
    ) -> tuple[bool, str, list[str]]:
        with self._lock:
            world, ontology = self._load_ontology()
            try:
                alumno = ontology.search_one(iri=f"{ontology.base_iri}{alumno_id}")
                materia = ontology.search_one(iri=f"{ontology.base_iri}{materia_id}")

                if alumno is None:
                    return (
                        False,
                        f"El alumno '{alumno_id}' no existe en la base de conocimiento semántica.",
                        [],
                    )
                if materia is None:
                    return (
                        False,
                        f"La materia '{materia_id}' no existe en la base de conocimiento semántica.",
                        [],
                    )

                if materia not in alumno.estaInscritoEn:
                    alumno.estaInscritoEn.append(materia)

                try:
                    with ontology:
                        owlready2.reasoning.sync_reasoner(
                            [ontology],
                            infer_property_values=True,
                        )
                except OwlReadyInconsistentOntologyError:
                    return (
                        False,
                        (
                            f"La inscripción de '{alumno_id}' en '{materia_id}' "
                            "produce una contradicción semántica."
                        ),
                        [],
                    )

                if Nothing in alumno.is_a:
                    return (
                        False,
                        (
                            f"El individuo '{alumno_id}' queda clasificado como "
                            "Nothing después de la inferencia."
                        ),
                        [],
                    )

                relaciones = list(
                    dict.fromkeys(
                        relacion.name for relacion in alumno.estaInscritoEn
                    )
                )
                return (
                    True,
                    "Inscripción semánticamente válida.",
                    relaciones,
                )
            finally:
                world.close()

ontology_service = OntologyService(
    owl_path=settings.ONTOLOGY_PATH,
    java_memory_mb=settings.REASONER_JAVA_MEMORY_MB,
)
