"""Pydantic v2 request/response contracts for the topics module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.topics.constants import ALLOWED_STATUS_VALUES, DEFAULT_ORDER_NUMBER
from app.modules.topics.validators import validate_order_number, validate_topic_title


class TopicCreateRequest(BaseModel):
    subject_id: uuid.UUID
    grade_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    order_number: int = DEFAULT_ORDER_NUMBER

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        return validate_topic_title(v)

    @field_validator("order_number")
    @classmethod
    def _order_number(cls, v: int) -> int:
        return validate_order_number(v)


class TopicUpdateRequest(BaseModel):
    grade_id: uuid.UUID | None = None
    title: str | None = None
    description: str | None = None
    order_number: int | None = None
    status: str | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, v: str | None) -> str | None:
        return validate_topic_title(v) if v is not None else None

    @field_validator("order_number")
    @classmethod
    def _order_number(cls, v: int | None) -> int | None:
        return validate_order_number(v) if v is not None else None

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_STATUS_VALUES:
            raise ValueError(f"status quyidagilardan biri bo'lishi kerak: {', '.join(ALLOWED_STATUS_VALUES)}")
        return v


class TopicOut(BaseModel):
    id: uuid.UUID
    subject_id: uuid.UUID
    grade_id: uuid.UUID | None
    title: str
    description: str | None
    order_number: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TopicListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    search: str | None = None
    subject_id: uuid.UUID | None = None
    grade_id: uuid.UUID | None = None
    status: str | None = None
    sort: str = "order_number"
