"""Pydantic request/response contracts for the users module."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.users.constants import ADMIN_SETTABLE_STATUSES
from app.modules.users.validators import validate_birth_date, validate_person_name


class UserOut(BaseModel):
    id: uuid.UUID
    role_id: uuid.UUID
    first_name: str
    last_name: str
    phone: str | None
    email: str | None
    gender: str | None
    birth_date: date | None
    image: str | None
    status: str
    last_login: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserSelfUpdateRequest(BaseModel):
    """What a user may change about themselves — no role, no status."""
    first_name: str | None = None
    last_name: str | None = None
    gender: str | None = None
    birth_date: date | None = None
    image: str | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def _names(cls, v: str | None) -> str | None:
        return validate_person_name(v) if v is not None else None

    @field_validator("birth_date")
    @classmethod
    def _birth_date(cls, v: date | None) -> date | None:
        return validate_birth_date(v)


class UserAdminUpdateRequest(BaseModel):
    """What an Admin may change about another user — includes status.
    role_id is intentionally NOT here: role changes go through a separate,
    Super-Admin-only endpoint (see router.py) so privilege escalation is
    never bundled with an ordinary profile edit."""
    first_name: str | None = None
    last_name: str | None = None
    status: str | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def _names(cls, v: str | None) -> str | None:
        return validate_person_name(v) if v is not None else None

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v is not None and v not in ADMIN_SETTABLE_STATUSES:
            raise ValueError(f"status quyidagilardan biri bo'lishi kerak: {', '.join(ADMIN_SETTABLE_STATUSES)}")
        return v


class UserRoleChangeRequest(BaseModel):
    """Super-Admin-only: reassign a user's role."""
    role_id: uuid.UUID


class UserListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    search: str | None = None
    role_id: uuid.UUID | None = None
    status: str | None = None
    sort: str = "-created_at"
