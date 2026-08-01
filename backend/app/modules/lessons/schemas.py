"""Pydantic v2 request/response contracts for the lessons module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.lessons.constants import ALLOWED_STATUS_VALUES
from app.modules.lessons.validators import validate_lesson_title, validate_media_url


class LessonCreateRequest(BaseModel):
    topic_id: uuid.UUID
    title: str
    video: str | None = None
    pdf: str | None = None
    content: str | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        return validate_lesson_title(v)

    @field_validator("video", "pdf")
    @classmethod
    def _urls(cls, v: str | None) -> str | None:
        return validate_media_url(v)

    @model_validator(mode="after")
    def _at_least_one_content_field(self) -> "LessonCreateRequest":
        if not (self.video or self.pdf or self.content):
            raise ValueError("Dars kamida bitta mazmun turiga ega bo'lishi kerak: video, pdf yoki content")
        return self


class LessonUpdateRequest(BaseModel):
    title: str | None = None
    video: str | None = None
    pdf: str | None = None
    content: str | None = None
    status: str | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, v: str | None) -> str | None:
        return validate_lesson_title(v) if v is not None else None

    @field_validator("video", "pdf")
    @classmethod
    def _urls(cls, v: str | None) -> str | None:
        return validate_media_url(v)

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_STATUS_VALUES:
            raise ValueError(f"status quyidagilardan biri bo'lishi kerak: {', '.join(ALLOWED_STATUS_VALUES)}")
        return v


class LessonOut(BaseModel):
    id: uuid.UUID
    topic_id: uuid.UUID
    title: str
    video: str | None
    pdf: str | None
    content: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LessonListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    search: str | None = None
    topic_id: uuid.UUID | None = None
    status: str | None = None
    sort: str = "-created_at"
