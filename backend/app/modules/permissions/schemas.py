"""Pydantic request/response contracts for the permissions module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.permissions.validators import (
    validate_module_name,
    validate_permission_code,
    validate_permission_name,
)


class PermissionCreateRequest(BaseModel):
    name: str
    code: str
    module: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return validate_permission_name(v)

    @field_validator("code")
    @classmethod
    def _code(cls, v: str) -> str:
        return validate_permission_code(v)

    @field_validator("module")
    @classmethod
    def _module(cls, v: str) -> str:
        return validate_module_name(v)


class PermissionUpdateRequest(BaseModel):
    """`code` is intentionally NOT updatable — every require_permission('CODE')
    call in the codebase depends on the code staying stable, exactly like
    role names in the roles module."""
    name: str | None = None
    description: str | None = None
    status: str | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        return validate_permission_name(v) if v is not None else None


class PermissionOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    module: str
    description: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PermissionListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    search: str | None = None
    module: str | None = None
    status: str | None = None
    sort: str = "module"


class RolePermissionAssignRequest(BaseModel):
    permission_id: uuid.UUID


class RolePermissionOut(BaseModel):
    id: uuid.UUID
    role_id: uuid.UUID
    permission_id: uuid.UUID
    permission: PermissionOut | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
