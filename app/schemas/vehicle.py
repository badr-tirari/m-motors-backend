from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


class VehicleCreate(BaseModel):
    """Payload pour POST /vehicles — back-office (US-07 : vente, US-08 : location)."""

    brand: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    motorization: str = Field(min_length=1, max_length=50)
    year: int = Field(ge=1990, le=2100)
    mileage_km: int = Field(ge=0)
    mode: VehicleMode
    price_eur: Decimal | None = Field(default=None, gt=0)
    monthly_price_eur: Decimal | None = Field(default=None, gt=0)
    # Reçu côté formulaire admin comme une liste de cases cochées (US-08) :
    # ["Assurance tous risques", "Entretien et SAV"] -> stocké normalisé en
    # chaîne "Assurance tous risques, Entretien et SAV".
    rental_included_services: list[str] | str | None = Field(default=None)

    @field_validator("rental_included_services", mode="after")
    @classmethod
    def join_services_list(cls, value: list[str] | str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip() or None
        cleaned = [item.strip() for item in value if item.strip()]
        return ", ".join(cleaned) if cleaned else None

    @model_validator(mode="after")
    def check_price_matches_mode(self) -> "VehicleCreate":
        if self.mode == VehicleMode.SALE and self.price_eur is None:
            raise ValueError("price_eur est obligatoire pour un véhicule en vente (mode=sale).")
        if self.mode == VehicleMode.RENTAL and self.monthly_price_eur is None:
            raise ValueError("monthly_price_eur est obligatoire pour un véhicule en location (mode=rental).")
        return self


