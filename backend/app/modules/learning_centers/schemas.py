"""Pydantic v2 request/response contracts for the learning_centers module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.learning_centers.constants import ALLOWED_STATUS_VALUES
from app.modules.learning_centers.validators import (
    validate_center_name,
    validate_institutional_phone,
    validate_owner_name,
)


class LearningCenterCreateRequest(BaseModel):
    name: str
    owner_name: str | None = None
    phone: str | None = None
    region: str | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return validate_center_name(v)

    @field_validator("owner_name")
    @classmethod
    def _owner_name(cls, v: str | None) -> str | None:
        return validate_owner_name(v)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        return validate_institutional_phone(v)


class LearningCenterUpdateRequest(BaseModel):
    name: str | None = None
    owner_name: str | None = None
    phone: str | None = None
    region: str | None = None
    status: str | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        return validate_center_name(v) if v is not None else None

    @field_validator("owner_name")
    @classmethod
    def _owner_name(cls, v: str | None) -> str | None:
        return validate_owner_name(v)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        return validate_institutional_phone(v)

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_STATUS_VALUES:
            raise ValueError(f"status quyidagilardan biri bo'lishi kerak: {', '.join(ALLOWED_STATUS_VALUES)}")
        return v


class LearningCenterOut(BaseModel):
    id: uuid.UUID
    name: str
    owner_name: str | None
    phone: str | None
    region: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LearningCenterListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    search: str | None = None
    region: str | None = None
    status: str | None = None
    sort: str = "name"
