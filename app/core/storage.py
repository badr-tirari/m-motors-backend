"""
Abstraction de stockage de fichiers. Implémentation locale pour le dev/tests ;
remplacée par Azure Blob Storage en production (voir US-14 — déploiement Azure).
Le code appelant (routers/dossiers.py) ne dépend que de cette interface, pas
de l'implémentation concrète : changer de backend de stockage n'impacte pas
le reste de l'application.
"""

import uuid
from pathlib import Path
from typing import Protocol

from app.core.config import settings


class FileStorage(Protocol):
    def save(self, content: bytes, original_filename: str, subdir: str) -> str:
        """Sauvegarde le contenu et retourne un identifiant/chemin de référence."""
        ...

    def read(self, stored_path: str) -> bytes:
        """Relit le contenu précédemment sauvegardé."""
        ...


class LocalFileStorage:
    """Stockage sur disque local — utilisé en dev et dans les tests."""

    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or settings.upload_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, content: bytes, original_filename: str, subdir: str) -> str:
        target_dir = self.base_dir / subdir
        target_dir.mkdir(parents=True, exist_ok=True)

        suffix = Path(original_filename).suffix
        unique_name = f"{uuid.uuid4()}{suffix}"
        target_path = target_dir / unique_name

        target_path.write_bytes(content)
        return str(Path(subdir) / unique_name)

    def read(self, stored_path: str) -> bytes:
        return (self.base_dir / stored_path).read_bytes()


def get_file_storage() -> FileStorage:
    """FastAPI dependency — point d'extension unique pour brancher Azure Blob Storage."""
    return LocalFileStorage()
