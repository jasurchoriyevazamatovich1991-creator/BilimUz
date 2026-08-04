"""Pydantic v2 request/response contracts for the schools module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.schools.constants import ALLOWED_STATUS_VALUES
from app.modules.schools.validators import validate_institutional_phone, validate_school_name


class SchoolCreateRequest(BaseModel):
    name: str
    region: str | None = None
    district: str | None = None
    address: str | None = None
    phone: str | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return validate_school_name(v)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        return validate_institutional_phone(v)


class SchoolUpdateRequest(BaseModel):
    name: str | None = None
    region: str | None = None
    district: str | None = None
    address: str | None = None
    phone: str | None = None
    status: str | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        return validate_school_name(v) if v is not None else None

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


class SchoolOut(BaseModel):
    id: uuid.UUID
    name: str
    region: str | None
    district: str | None
    address: str | None
    phone: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SchoolListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    search: str | None = None
    region: str | None = None
    district: str | None = None
    status: str | None = None
    sort: str = "name"
