from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, Token
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


@router.post("/login", response_model=Token, summary="Se connecter (US-02)")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> Token:
    """
    En tant que client, je veux me connecter à mon compte afin d'accéder
    à mon espace personnel.

    Critères d'acceptation (MMOT-8) :
    - authentification JWT
    - message d'erreur clair si identifiants invalides (401, sans préciser
      si c'est l'email ou le mot de passe qui est incorrect — anti-énumération)
    """
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
        )

    access_token = create_access_token({"sub": user.id, "role": user.role.value})
    return Token(access_token=access_token)


@router.get("/me", response_model=UserOut, summary="Profil de l'utilisateur connecté")
def read_me(current_user: User = Depends(get_current_user)) -> User:
    """Retourne le profil associé au token JWT fourni (vérifie le rôle, US-02)."""
    return current_user


@router.get("/admin-check", summary="Démonstration de la garde de rôle admin")
def admin_check(current_user: User = Depends(require_admin)) -> dict[str, str]:
    """
    Endpoint de démonstration : accessible uniquement aux comptes "admin".
    Réutilisé par les futures routes back-office (US-07 à US-11).
    """
    return {"message": f"Accès admin confirmé pour {current_user.email}"}

