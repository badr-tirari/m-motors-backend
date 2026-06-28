import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    # Référence de l'ancien système (table "vehicules_stock") — permet à l'ETL
    # de migration (US-12) d'être idempotent : un re-run ne crée pas de doublons.
    legacy_ref: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    mode_changes: Mapped[list["VehicleModeChange"]] = relationship(
        back_populates="vehicle", cascade="all, delete-orphan", order_by="VehicleModeChange.changed_at"
    )


class VehicleModeChange(Base):
    """Historique des bascules vente <-> location d'un véhicule (US-09)."""

    __tablename__ = "vehicle_mode_changes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    vehicle_id: Mapped[str] = mapped_column(String(36), ForeignKey("vehicles.id"), nullable=False, index=True)

    previous_mode: Mapped[VehicleMode] = mapped_column(Enum(VehicleMode), nullable=False)
    new_mode: Mapped[VehicleMode] = mapped_column(Enum(VehicleMode), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    vehicle: Mapped["Vehicle"] = relationship(back_populates="mode_changes")

