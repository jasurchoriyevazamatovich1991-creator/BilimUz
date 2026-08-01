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
