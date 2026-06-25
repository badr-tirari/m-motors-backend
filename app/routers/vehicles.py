from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.vehicle import Vehicle, VehicleMode, VehicleStatus
from app.schemas.vehicle import PaginatedVehicles

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


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
