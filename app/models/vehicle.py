import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VehicleMode(str, enum.Enum):
    SALE = "sale"
    RENTAL = "rental"


class VehicleStatus(str, enum.Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    SOLD = "sold"


class Vehicle(Base):
    """Un véhicule du catalogue M-Motors, proposé à la vente ou à la location longue durée."""

    __tablename__ = "vehicles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    brand: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    motorization: Mapped[str] = mapped_column(String(50), nullable=False)  # Essence/Diesel/Électrique/Hybride
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    mileage_km: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    mode: Mapped[VehicleMode] = mapped_column(Enum(VehicleMode), nullable=False, index=True)
    status: Mapped[VehicleStatus] = mapped_column(
        Enum(VehicleStatus), nullable=False, default=VehicleStatus.AVAILABLE, index=True
    )

    # Achat : price_eur renseigné. Location longue durée : monthly_price_eur renseigné.
    price_eur: Mapped[int | None] = mapped_column(Numeric(10, 2), nullable=True)
    monthly_price_eur: Mapped[int | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Liste de services inclus pour la location (séparés par virgule) — voir US-08.
    rental_included_services: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
