"""
Abstraction de notification par email. ConsoleEmailNotifier (logging) en dev
et tests ; à remplacer par un vrai backend SMTP en production (Badr dispose
déjà d'un envoi Gmail SMTP fonctionnel sur un autre projet — même principe
de branchement que pour FileStorage / Azure Blob Storage, voir US-14).
"""

import logging
from typing import Protocol

logger = logging.getLogger("notifications")


class EmailNotifier(Protocol):
    def send(self, to: str, subject: str, body: str) -> bool: ...


class ConsoleEmailNotifier:
    """Notifieur de dev/tests : journalise l'email au lieu de l'envoyer réellement."""

    def send(self, to: str, subject: str, body: str) -> bool:
        logger.info("EMAIL -> %s | %s | %s", to, subject, body)
        return True


def get_email_notifier() -> EmailNotifier:
    """FastAPI dependency — point d'extension unique pour brancher un vrai SMTP."""
    return ConsoleEmailNotifier()
