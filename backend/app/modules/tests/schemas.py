"""Pydantic v2 request/response contracts for the tests module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.tests.validators import validate_duration, validate_passing_score, validate_test_title


class TestCreateRequest(BaseModel):
    subject_id: uuid.UUID | None = None
    grade_id: uuid.UUID | None = None
    topic_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    difficulty: str = "medium"
    duration: int = 60
    passing_score: float | None = None
    shuffle_questions: bool = True
    shuffle_answers: bool = True
    # Sprint 45 — optional. None (the default) keeps the exact existing
    # behavior (platform default DEFAULT_MAX_ATTEMPTS = 1).
    max_attempts: int | None = None
    # Sprint 47 — optional, generic. No IELTS-specific enum.
    exam_variant: str | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        return validate_test_title(v)

    @field_validator("duration")
    @classmethod
    def _duration(cls, v: int) -> int:
        return validate_duration(v)

    @field_validator("passing_score")
    @classmethod
    def _passing_score(cls, v: float | None) -> float | None:
        return validate_passing_score(v)

    @field_validator("max_attempts")
    @classmethod
    def _max_attempts(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("max_attempts kamida 1 bo'lishi kerak")
        return v

    @field_validator("difficulty")
    @classmethod
    def _difficulty(cls, v: str) -> str:
        if v not in ("easy", "medium", "hard"):
            raise ValueError("difficulty quyidagilardan biri bo'lishi kerak: easy, medium, hard")
        return v


class TestUpdateRequest(BaseModel):
    subject_id: uuid.UUID | None = None
    grade_id: uuid.UUID | None = None
    topic_id: uuid.UUID | None = None
    title: str | None = None
    description: str | None = None
    difficulty: str | None = None
    duration: int | None = None
    passing_score: float | None = None
    shuffle_questions: bool | None = None
    shuffle_answers: bool | None = None
    max_attempts: int | None = None
    exam_variant: str | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, v: str | None) -> str | None:
        return validate_test_title(v) if v is not None else None

    @field_validator("duration")
    @classmethod
    def _duration(cls, v: int | None) -> int | None:
        return validate_duration(v) if v is not None else None

    @field_validator("passing_score")
    @classmethod
    def _passing_score(cls, v: float | None) -> float | None:
        return validate_passing_score(v)

    @field_validator("max_attempts")
    @classmethod
    def _max_attempts(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("max_attempts kamida 1 bo'lishi kerak")
        return v


class TestPublishRequest(BaseModel):
    """Empty body — publishing is a state transition, not a data edit.
    Kept as a distinct schema (not just an empty POST) for consistency
    with the rest of the API and to leave room for future fields
    (e.g. a scheduled publish_at) without a breaking change."""
    pass


class TestOut(BaseModel):
    id: uuid.UUID
    subject_id: uuid.UUID | None
    grade_id: uuid.UUID | None
    topic_id: uuid.UUID | None
    title: str
    description: str | None
    difficulty: str
    duration: int
    question_count: int
    passing_score: float | None
    shuffle_questions: bool
    shuffle_answers: bool
    status: str
    max_attempts: int | None
    exam_variant: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TestListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    search: str | None = None
    subject_id: uuid.UUID | None = None
    grade_id: uuid.UUID | None = None
    topic_id: uuid.UUID | None = None
    difficulty: str | None = None
    status: str | None = None
    sort: str = "-created_at"


# --- Sprint 51: ExamSection / ExamModule Admin Configuration API ---

class ExamSectionCreateRequest(BaseModel):
    test_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    order_number: int = Field(default=0, ge=0)
    duration: int | None = Field(default=None, gt=0)


class ExamSectionUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    order_number: int | None = Field(default=None, ge=0)
    duration: int | None = Field(default=None, gt=0)


class ExamSectionOut(BaseModel):
    id: uuid.UUID
    test_id: uuid.UUID
    name: str
    order_number: int
    duration: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExamModuleCreateRequest(BaseModel):
    section_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    order_number: int = Field(default=0, ge=0)
    duration: int | None = Field(default=None, gt=0)
    difficulty_tier: str | None = Field(default=None, max_length=20)
    # Sprint 48/51 — generic metadata only, no exam-specific validation.
    # Any string value is accepted; this schema never checks against
    # SAT/GRE/IELTS-specific names.
    routing_group: str | None = Field(default=None, max_length=50)
    routing_variant: str | None = Field(default=None, max_length=50)


class ExamModuleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    order_number: int | None = Field(default=None, ge=0)
    duration: int | None = Field(default=None, gt=0)
    difficulty_tier: str | None = Field(default=None, max_length=20)
    routing_group: str | None = Field(default=None, max_length=50)
    routing_variant: str | None = Field(default=None, max_length=50)


class ExamModuleOut(BaseModel):
    id: uuid.UUID
    section_id: uuid.UUID
    name: str
    order_number: int
    duration: int | None
    difficulty_tier: str | None
    routing_group: str | None
    routing_variant: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
