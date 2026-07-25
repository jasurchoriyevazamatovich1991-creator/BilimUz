"""Pydantic request/response contracts for the subjects module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.subjects.constants import ALLOWED_STATUS_VALUES
from app.modules.subjects.validators import validate_hex_color, validate_subject_name


class SubjectCreateRequest(BaseModel):
    name: str
    icon: str | None = None
    color: str | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return validate_subject_name(v)

    @field_validator("color")
    @classmethod
    def _color(cls, v: str | None) -> str | None:
        return validate_hex_color(v)


class SubjectUpdateRequest(BaseModel):
    name: str | None = None
    icon: str | None = None
    color: str | None = None
    status: str | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        return validate_subject_name(v) if v is not None else None

    @field_validator("color")
    @classmethod
    def _color(cls, v: str | None) -> str | None:
        return validate_hex_color(v)

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_STATUS_VALUES:
            raise ValueError(f"status quyidagilardan biri bo'lishi kerak: {', '.join(ALLOWED_STATUS_VALUES)}")
        return v


class SubjectOut(BaseModel):
    id: uuid.UUID
    name: str
    icon: str | None
    color: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SubjectListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    search: str | None = None
    status: str | None = None
    sort: str = "-created_at"
