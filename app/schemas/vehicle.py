from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.vehicle import VehicleMode, VehicleStatus


class VehicleOut(BaseModel):
    """Représentation publique d'un véhicule (résultat de recherche / fiche détaillée)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    brand: str
    model: str
    motorization: str
    year: int
    mileage_km: int
    mode: VehicleMode
    status: VehicleStatus
    price_eur: Decimal | None
    monthly_price_eur: Decimal | None
    rental_included_services: str | None
    created_at: datetime


class PaginatedVehicles(BaseModel):
    """Réponse paginée pour GET /vehicles (US-03)."""

    items: list[VehicleOut]
    total: int
    page: int
    page_size: int
