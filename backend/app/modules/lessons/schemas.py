"""Pydantic v2 request/response contracts for the lessons module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.lessons.constants import ALLOWED_STATUS_VALUES
from app.modules.lessons.validators import validate_lesson_title, validate_media_url, validate_order_number


class LessonCreateRequest(BaseModel):
    topic_id: uuid.UUID
    title: str
    video: str | None = None
    pdf: str | None = None
    content: str | None = None
    # Sprint 38 — optional. When omitted, the service assigns the next
    # available order_number within this topic (current max + 1) so a
    # Teacher/Admin creating lessons one at a time never has to think
    # about numbering — matches the existing UX (order isn't manually
    # tracked today either). An explicit value is still honored if given.
    order_number: int | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        return validate_lesson_title(v)

    @field_validator("video", "pdf")
    @classmethod
    def _urls(cls, v: str | None) -> str | None:
        return validate_media_url(v)

    @field_validator("order_number")
    @classmethod
    def _order_number(cls, v: int | None) -> int | None:
        return validate_order_number(v) if v is not None else None

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
    # Sprint 35 — additive. Set after a real R2 upload finalizes (the
    # Lesson must already exist for this to be meaningful — matches
    # why this is on Update, not Create). Omitting the field entirely
    # leaves it unchanged (`exclude_unset=True` in the service);
    # explicitly sending `null` clears it (removes the R2 video,
    # falling back to the legacy `video` URL field if present).
    video_upload_id: uuid.UUID | None = None
    # Sprint 38 — additive. Omitting the field leaves order_number
    # unchanged; a DB-level UNIQUE(topic_id, order_number) violation
    # (another lesson in the same topic already has this number) is
    # surfaced as a clear conflict error, not a silent overwrite.
    order_number: int | None = None

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

    @field_validator("order_number")
    @classmethod
    def _order_number(cls, v: int | None) -> int | None:
        return validate_order_number(v) if v is not None else None


class LessonOut(BaseModel):
    id: uuid.UUID
    topic_id: uuid.UUID
    title: str
    video: str | None
    video_upload_id: uuid.UUID | None
    pdf: str | None
    content: str | None
    order_number: int
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
    # Sprint 38 — default changed from "-created_at" to "order_number":
    # deterministic, curriculum-meaningful ordering is now the sensible
    # default for a content-browsing list. Any caller can still pass an
    # explicit `sort` param to get the old behavior.
    sort: str = "order_number"
