from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db.session import get_db
from app.models.user import User
from app.models.vehicle import Vehicle, VehicleMode, VehicleModeChange, VehicleStatus
from app.schemas.vehicle import PaginatedVehicles, ToggleModePayload, VehicleCreate, VehicleOut

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.post(
    "",
    response_model=VehicleOut,
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter un véhicule à la vente ou à la location (US-07, US-08)",
)
def create_vehicle(
    payload: VehicleCreate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> Vehicle:
    """
    En tant qu'admin, je veux ajouter un véhicule à la vente (US-07) ou à la
    location longue durée (US-08) afin de l'exposer dans le catalogue.

    Critères d'acceptation (MMOT-14, MMOT-15) :
    - réservé aux comptes admin (403 sinon)
    - prix obligatoire pour la vente, mensualité obligatoire pour la location
      (validé par le schéma VehicleCreate)
    - le véhicule créé est immédiatement visible dans le catalogue (status=available)
    """
    vehicle = Vehicle(**payload.model_dump(), status=VehicleStatus.AVAILABLE)
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle



@router.get("", response_model=PaginatedVehicles, summary="Rechercher des véhicules (US-03)")
def search_vehicles(
    db: Annotated[Session, Depends(get_db)],
    mode: VehicleMode | None = Query(None, description="achat (sale) ou location (rental)"),
    brand: str | None = Query(None, description="Filtre par marque (recherche partielle)"),
    price_min: float | None = Query(None, ge=0),
    price_max: float | None = Query(None, ge=0),
    mileage_max: int | None = Query(None, ge=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
) -> PaginatedVehicles:
    """
    En tant que visiteur, je veux rechercher des véhicules par mode (achat/location),
    marque, prix et kilométrage afin de trouver un véhicule adapté à mon besoin.

    Critères d'acceptation (MMOT-9) :
    - filtres combinables (mode, marque, prix, km)
    - résultats paginés

    Seuls les véhicules au statut "available" sont retournés : le catalogue
    public ne montre pas les véhicules déjà vendus/réservés.
    """
    conditions = [Vehicle.status == VehicleStatus.AVAILABLE]

    if mode is not None:
        conditions.append(Vehicle.mode == mode)
    if brand:
        conditions.append(Vehicle.brand.ilike(f"%{brand}%"))
    if price_min is not None:
        conditions.append(Vehicle.price_eur >= price_min)
    if price_max is not None:
        conditions.append(Vehicle.price_eur <= price_max)
    if mileage_max is not None:
        conditions.append(Vehicle.mileage_km <= mileage_max)

    base_query = select(Vehicle).where(*conditions)

    total = db.scalar(select(func.count()).select_from(base_query.subquery())) or 0

    items = db.scalars(
        base_query.order_by(Vehicle.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    return PaginatedVehicles(items=list(items), total=total, page=page, page_size=page_size)


@router.get(
    "/{vehicle_id}",
    response_model=VehicleOut,
    summary="Consulter la fiche détaillée d'un véhicule (US-04)",
)
def get_vehicle(vehicle_id: str, db: Annotated[Session, Depends(get_db)]) -> Vehicle:
    """
    En tant que visiteur, je veux consulter la fiche détaillée d'un véhicule
    afin d'avoir toutes les infos avant de déposer un dossier.

    Critères d'acceptation (MMOT-10) :
    - fiche avec caractéristiques complètes, prix ou mensualité selon le mode
    - 404 explicite si le véhicule n'existe pas
    """
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Véhicule introuvable.")
    return vehicle


@router.patch(
    "/{vehicle_id}/toggle-mode",
    response_model=VehicleOut,
    summary="Basculer un véhicule vente ↔ location (US-09)",
)
def toggle_vehicle_mode(
    vehicle_id: str,
    payload: ToggleModePayload,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> Vehicle:
    """
    En tant qu'admin, je veux basculer un véhicule de vente vers location (et
    inversement) afin d'adapter l'offre commerciale sans recréer la fiche.

    Critères d'acceptation (MMOT-16) :
    - le nouveau prix (price_eur ou monthly_price_eur selon le nouveau mode)
      doit être fourni si le véhicule ne l'avait pas déjà
    - l'historique du changement de mode est conservé (VehicleModeChange)
    """
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Véhicule introuvable.")

    new_mode = VehicleMode.RENTAL if vehicle.mode == VehicleMode.SALE else VehicleMode.SALE

    if new_mode == VehicleMode.SALE:
        new_price = payload.price_eur or vehicle.price_eur
        if new_price is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="price_eur est requis pour basculer ce véhicule en vente.",
            )
        vehicle.price_eur = new_price
    else:
        new_monthly = payload.monthly_price_eur or vehicle.monthly_price_eur
        if new_monthly is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="monthly_price_eur est requis pour basculer ce véhicule en location.",
            )
        vehicle.monthly_price_eur = new_monthly
        if payload.rental_included_services is not None:
            vehicle.rental_included_services = payload.rental_included_services

    db.add(VehicleModeChange(vehicle_id=vehicle.id, previous_mode=vehicle.mode, new_mode=new_mode))
    vehicle.mode = new_mode

    db.commit()
    db.refresh(vehicle)
    return vehicle


