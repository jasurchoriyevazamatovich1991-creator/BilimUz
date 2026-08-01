"""Pydantic v2 request/response contracts for the questions module
(Question, QuestionOption, QuestionMedia)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.questions.constants import ALLOWED_DIFFICULTY_LEVELS, ALLOWED_MEDIA_TYPES, ALLOWED_QUESTION_TYPES
from app.modules.questions.validators import (
    validate_media_url,
    validate_option_set,
    validate_option_text,
    validate_question_text,
    validate_score,
)

# --- Options -----------------------------------------------------------

class OptionCreateRequest(BaseModel):
    option_text: str
    is_correct: bool = False

    @field_validator("option_text")
    @classmethod
    def _text(cls, v: str) -> str:
        return validate_option_text(v)


class OptionUpdateRequest(BaseModel):
    option_text: str | None = None
    is_correct: bool | None = None

    @field_validator("option_text")
    @classmethod
    def _text(cls, v: str | None) -> str | None:
        return validate_option_text(v) if v is not None else None


class OptionOut(BaseModel):
    id: uuid.UUID
    question_id: uuid.UUID
    option_text: str
    is_correct: bool

    model_config = {"from_attributes": True}


# --- Media ---------------------------------------------------------------

class MediaCreateRequest(BaseModel):
    media_type: str
    file_url: str

    @field_validator("media_type")
    @classmethod
    def _type(cls, v: str) -> str:
        if v not in ALLOWED_MEDIA_TYPES:
            raise ValueError(f"media_type quyidagilardan biri bo'lishi kerak: {', '.join(ALLOWED_MEDIA_TYPES)}")
        return v

    @field_validator("file_url")
    @classmethod
    def _url(cls, v: str) -> str:
        return validate_media_url(v)


class MediaOut(BaseModel):
    id: uuid.UUID
    question_id: uuid.UUID
    media_type: str
    file_url: str

    model_config = {"from_attributes": True}


# --- Questions -----------------------------------------------------------

class QuestionCreateRequest(BaseModel):
    test_id: uuid.UUID
    question_text: str
    question_type: str = "single_choice"
    difficulty: str = "medium"
    score: float = 1
    explanation: str | None = None
    options: list[OptionCreateRequest] = Field(default_factory=list)

    @field_validator("question_text")
    @classmethod
    def _text(cls, v: str) -> str:
        return validate_question_text(v)

    @field_validator("question_type")
    @classmethod
    def _type(cls, v: str) -> str:
        if v not in ALLOWED_QUESTION_TYPES:
            raise ValueError(f"question_type quyidagilardan biri bo'lishi kerak: {', '.join(ALLOWED_QUESTION_TYPES)}")
        return v

    @field_validator("difficulty")
    @classmethod
    def _difficulty(cls, v: str) -> str:
        if v not in ALLOWED_DIFFICULTY_LEVELS:
            raise ValueError(f"difficulty quyidagilardan biri bo'lishi kerak: {', '.join(ALLOWED_DIFFICULTY_LEVELS)}")
        return v

    @field_validator("score")
    @classmethod
    def _score(cls, v: float) -> float:
        return validate_score(v)

    @model_validator(mode="after")
    def _validate_options(self) -> "QuestionCreateRequest":
        validate_option_set(self.question_type, [o.model_dump() for o in self.options])
        return self


class QuestionUpdateRequest(BaseModel):
    question_text: str | None = None
    difficulty: str | None = None
    score: float | None = None
    explanation: str | None = None
    status: str | None = None

    @field_validator("question_text")
    @classmethod
    def _text(cls, v: str | None) -> str | None:
        return validate_question_text(v) if v is not None else None

    @field_validator("score")
    @classmethod
    def _score(cls, v: float | None) -> float | None:
        return validate_score(v) if v is not None else None


class QuestionOut(BaseModel):
    id: uuid.UUID
    test_id: uuid.UUID
    question_text: str
    question_type: str
    difficulty: str
    score: float
    explanation: str | None
    status: str
    options: list[OptionOut] = []
    media: list[MediaOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QuestionOutNoAnswers(BaseModel):
    """Same as QuestionOut but WITHOUT is_correct on options and WITHOUT
    explanation — used when a student is actively taking a test (see the
    `attempts` module). Never reuse QuestionOut for that path."""
    id: uuid.UUID
    question_text: str
    question_type: str
    score: float

    model_config = {"from_attributes": True}


class QuestionListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    test_id: uuid.UUID | None = None
    difficulty: str | None = None
    status: str | None = None
    sort: str = "created_at"
