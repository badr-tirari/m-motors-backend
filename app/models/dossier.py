import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.vehicle import VehicleMode


class DossierStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Dossier(Base):
    """Un dossier d'achat ou de location déposé par un client pour un véhicule donné."""

    __tablename__ = "dossiers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    vehicle_id: Mapped[str] = mapped_column(String(36), ForeignKey("vehicles.id"), nullable=False, index=True)

    # Capturé au moment du dépôt (snapshot) : un dossier "achat" reste un dossier
    # "achat" même si le véhicule bascule en location ensuite (US-09).
    type: Mapped[VehicleMode] = mapped_column(Enum(VehicleMode), nullable=False)
    status: Mapped[DossierStatus] = mapped_column(
        Enum(DossierStatus), nullable=False, default=DossierStatus.PENDING, index=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    documents: Mapped[list["DossierDocument"]] = relationship(
        back_populates="dossier", cascade="all, delete-orphan"
    )
    status_events: Mapped[list["DossierStatusEvent"]] = relationship(
        back_populates="dossier", cascade="all, delete-orphan", order_by="DossierStatusEvent.created_at"
    )


class DossierDocument(Base):
    """Un document joint à un dossier (pièce d'identité, justificatif de domicile, etc.)."""

    __tablename__ = "dossier_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dossier_id: Mapped[str] = mapped_column(String(36), ForeignKey("dossiers.id"), nullable=False, index=True)

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    dossier: Mapped["Dossier"] = relationship(back_populates="documents")


class DossierStatusEvent(Base):
    """Historique des changements de statut d'un dossier (US-06 : 'historique conservé')."""

    __tablename__ = "dossier_status_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dossier_id: Mapped[str] = mapped_column(String(36), ForeignKey("dossiers.id"), nullable=False, index=True)

    status: Mapped[DossierStatus] = mapped_column(Enum(DossierStatus), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    dossier: Mapped["Dossier"] = relationship(back_populates="status_events")
