"""Pydantic v2 request/response contracts for the grades module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.grades.constants import ALLOWED_STATUS_VALUES
from app.modules.grades.validators import validate_grade_name


class GradeCreateRequest(BaseModel):
    name: str = Field(..., examples=["5-sinf"], description="Sinf/daraja nomi (noyob)")

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return validate_grade_name(v)


class GradeUpdateRequest(BaseModel):
    """`name` is intentionally NOT updatable here — see roles/subjects
    modules for the same rule: renaming in place could silently break
    anything referencing the old name elsewhere."""
    status: str | None = None

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_STATUS_VALUES:
            raise ValueError(f"status quyidagilardan biri bo'lishi kerak: {', '.join(ALLOWED_STATUS_VALUES)}")
        return v


class GradeOut(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GradeListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    search: str | None = None
    status: str | None = None
    sort: str = "name"
