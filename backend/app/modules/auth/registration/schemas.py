"""
Request/response contracts for the isolated Register API. Password
strength is deliberately NOT validated via a Pydantic field_validator
here (unlike the existing RegisterRequest in auth/schemas.py) — it's
checked in the service layer via PasswordService.validate_password_strength(),
which returns ALL violated rules at once instead of Pydantic surfacing
only the first ValueError.
"""
from datetime import datetime
import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.modules.auth.jwt.schemas import TokenPair
from app.modules.auth.validators import validate_uzbek_phone


class RegistrationRequest(BaseModel):
    first_name: str = Field(min_length=2, max_length=100)
    last_name: str = Field(min_length=2, max_length=100)
    phone: str
    email: EmailStr | None = None
    password: str  # strength checked in service, not here

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return validate_uzbek_phone(v)


class RegisteredUserOut(BaseModel):
    """No password_hash field — this is the whole point of the
    'return created user (without password)' requirement."""
    id: uuid.UUID
    first_name: str
    last_name: str
    phone: str | None
    email: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RegistrationResponse(BaseModel):
    user: RegisteredUserOut
    tokens: TokenPair
