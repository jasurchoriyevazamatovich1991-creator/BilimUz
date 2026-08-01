"""Pydantic request/response contracts for the auth module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.modules.auth.validators import validate_password_strength, validate_uzbek_phone


class RegisterRequest(BaseModel):
    first_name: str = Field(min_length=2, max_length=100)
    last_name: str = Field(min_length=2, max_length=100)
    phone: str
    email: EmailStr | None = None
    password: str = Field(min_length=12, max_length=72)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return validate_uzbek_phone(v)

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        return validate_password_strength(v)


class VerifyRequest(BaseModel):
    user_id: uuid.UUID
    code: str = Field(min_length=6, max_length=6)


class LoginRequest(BaseModel):
    identifier: str  # phone or email
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=72)

    @field_validator("new_password")
    @classmethod
    def _new_password(cls, v: str) -> str:
        return validate_password_strength(v)


class SessionOut(BaseModel):
    id: uuid.UUID
    device: str | None
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserPublic(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    phone: str | None
    email: str | None
    status: str
    role_id: uuid.UUID

    model_config = {"from_attributes": True}
