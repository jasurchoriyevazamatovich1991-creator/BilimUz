"""Pydantic request/response contracts for the roles module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.roles.validators import validate_role_name


class RoleCreateRequest(BaseModel):
    name: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return validate_role_name(v)


class RoleUpdateRequest(BaseModel):
    description: str | None = None
    status: str | None = None
    # `name` is intentionally NOT updatable here — renaming a role is
    # handled as create-new + migrate-users, never an in-place edit,
    # because every require_roles("Exact Name") call across the codebase
    # depends on the name staying stable. See SystemRoleProtectedException
    # for why system roles can't even go through that path.


class RoleOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    search: str | None = None
    status: str | None = None
    sort: str = "name"
