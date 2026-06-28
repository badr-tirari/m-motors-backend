from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.dossier import DossierStatus
from app.models.vehicle import VehicleMode


class DossierCreate(BaseModel):
    """Payload pour POST /dossiers (US-05)."""

    vehicle_id: str = Field(min_length=1)


class DossierDecision(BaseModel):
    """Payload pour PATCH /dossiers/{id}/decision (US-11)."""

    decision: DossierStatus = Field(description="'approved' ou 'rejected' uniquement")
    reason: str | None = Field(default=None, max_length=1000, description="Motif, optionnel")



class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    content_type: str
    uploaded_at: datetime


class StatusEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: DossierStatus
    reason: str | None
    created_at: datetime


class DossierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    vehicle_id: str
    type: VehicleMode
    status: DossierStatus
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
    documents: list[DocumentOut] = []
    status_events: list[StatusEventOut] = []
