from fastapi import FastAPI

from app.db.base import Base
from app.db.session import engine
from app.routers import auth

# Crée les tables si elles n'existent pas encore (dev). En production,
# la création/migration du schéma est gérée séparément (cf. US-12, US-14).
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="M-Motors API",
    description="API de la refonte digitale M-Motors (achat / location longue durée).",
    version="0.1.0",
)

app.include_router(auth.router, prefix="/api")


@app.get("/health", tags=["monitoring"])
def health() -> dict[str, str]:
    """Endpoint de supervision basique (étendu en US-16)."""
    return {"status": "ok"}
