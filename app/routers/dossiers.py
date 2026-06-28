from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.storage import FileStorage, get_file_storage
from app.db.session import get_db
from app.models.dossier import Dossier, DossierDocument, DossierStatus, DossierStatusEvent
from app.models.user import User
from app.models.vehicle import Vehicle
from app.schemas.dossier import DocumentOut, DossierCreate, DossierOut

router = APIRouter(prefix="/dossiers", tags=["dossiers"])

MAX_DOCUMENT_SIZE_BYTES = 10 * 1024 * 1024  # 10 Mo
ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}


@router.get(
    "/me",
    response_model=list[DossierOut],
    summary="Lister mes dossiers (US-06)",
)
def list_my_dossiers(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[Dossier]:
    """
    En tant que client, je veux suivre l'avancement de mon dossier depuis mon
    espace personnel afin de savoir où en est ma demande.

    Critères d'acceptation (MMOT-13) :
    - statuts visibles : en attente / validé / refusé
    - liste triée du plus récent au plus ancien
    """
    return list(
        db.scalars(
            select(Dossier).where(Dossier.client_id == current_user.id).order_by(Dossier.created_at.desc())
        ).all()
    )


@router.get(
    "/{dossier_id}",
    response_model=DossierOut,
    summary="Consulter un dossier et son historique (US-06)",
)
def get_dossier(
    dossier_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Dossier:
    """
    Critères d'acceptation (MMOT-13) :
    - historique des changements de statut consultable (`status_events`)
    - seul le propriétaire du dossier peut le consulter
    """
    dossier = db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier introuvable.")
    if dossier.client_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ce dossier ne vous appartient pas.")
    return dossier


@router.post(
    "",
    response_model=DossierOut,
    status_code=status.HTTP_201_CREATED,
    summary="Déposer un dossier d'achat ou de location (US-05)",
)
def create_dossier(
    payload: DossierCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Dossier:
    """
    En tant que client, je veux déposer un dossier d'achat ou de location avec
    mes documents afin de soumettre ma demande sans me déplacer.

    Critères d'acceptation (MMOT-12) :
    - dossier créé avec statut "en attente" (pending)
    - le type (achat/location) est calqué sur le mode du véhicule au moment du dépôt
    """
    vehicle = db.get(Vehicle, payload.vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Véhicule introuvable.")

    existing_pending = db.scalar(
        select(Dossier).where(
            Dossier.client_id == current_user.id,
            Dossier.vehicle_id == vehicle.id,
            Dossier.status == DossierStatus.PENDING,
        )
    )
    if existing_pending is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vous avez déjà un dossier en attente pour ce véhicule.",
        )

    dossier = Dossier(client_id=current_user.id, vehicle_id=vehicle.id, type=vehicle.mode)
    db.add(dossier)
    db.flush()  # pour obtenir dossier.id avant le commit

    db.add(DossierStatusEvent(dossier_id=dossier.id, status=DossierStatus.PENDING))
    db.commit()
    db.refresh(dossier)
    return dossier



@router.post(
    "/{dossier_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter un document à un dossier (US-05)",
)
async def upload_document(
    dossier_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_file_storage)],
    file: UploadFile,
) -> DossierDocument:
    """
    Critères d'acceptation (MMOT-12) :
    - upload multi-documents (pièce d'identité, justificatif de domicile, etc.)
    - stockage sécurisé (abstraction FileStorage — Azure Blob Storage en prod, voir US-14)
    - seul le propriétaire du dossier peut y ajouter un document
    """
    dossier = db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier introuvable.")
    if dossier.client_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ce dossier ne vous appartient pas.")

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Format non accepté (PDF, JPEG ou PNG uniquement).",
        )

    content = await file.read()
    if len(content) > MAX_DOCUMENT_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Fichier trop volumineux (10 Mo max).")

    stored_path = storage.save(content, file.filename or "document", subdir=f"dossiers/{dossier.id}")

    document = DossierDocument(
        dossier_id=dossier.id,
        original_filename=file.filename or "document",
        content_type=file.content_type,
        stored_path=stored_path,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document
