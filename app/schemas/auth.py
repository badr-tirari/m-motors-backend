from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """Payload pour POST /auth/login (US-02)."""

    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
