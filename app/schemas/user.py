from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserCreate(BaseModel):
    """Payload for POST /auth/register (US-01)."""

    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Minimum 8 caractères.",
    )


class UserOut(BaseModel):
    """Public representation of a user — never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    created_at: datetime
