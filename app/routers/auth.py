from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un compte client (US-01)",
)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    """
    En tant que visiteur, je veux créer un compte client afin de pouvoir
    déposer un dossier d'achat ou de location.

    Critères d'acceptation (MMOT-7) :
    - email unique en base
    - mot de passe hashé (jamais stocké en clair)
    - validation des entrées côté API (email, longueur du mot de passe)
    """
    existing_user = db.scalar(select(User).where(User.email == payload.email))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte existe déjà avec cet email.",
        )

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
