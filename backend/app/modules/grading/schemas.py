"""Task 5 — grading DTOs. Request schemas accept ONLY grader-editable
fields: grader_id, status, rubric_id, revision data and finalization
timestamps are always set by the server (extra fields are rejected)."""
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.grading.constants import MAX_FEEDBACK_LENGTH, MAX_INSTRUCTIONS_LENGTH, MAX_NOTES_LENGTH, MAX_REASON_LENGTH


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- rubrics ---

class RubricCriterionIn(_Strict):
    key: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=100)
    min: Decimal
    max: Decimal
    step: Decimal
    weight: Decimal = Decimal(1)


class RubricCreateRequest(_Strict):
    score_component: str
    name: str = Field(min_length=1, max_length=150)
    criteria: list[RubricCriterionIn] = Field(min_length=1, max_length=10)
    rounding: str = "half_up"
    instructions: str | None = Field(default=None, max_length=MAX_INSTRUCTIONS_LENGTH)
    # Admin attests the rubric matches a validated official source. False
    # makes every score produced with it provisional.
    is_validated: bool = False


class RubricCriterionOut(BaseModel):
    key: str
    label: str
    min: str
    max: str
    step: str
    weight: str


class RubricOut(BaseModel):
    id: uuid.UUID
    score_component: str
    version: int
    name: str
    criteria: list[RubricCriterionOut]
    rounding: str
    instructions: str | None
    is_validated: bool
    is_current: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


# --- reviews ---

class DraftSaveRequest(_Strict):
    criterion_scores: dict[str, Decimal] = Field(default_factory=dict)
    feedback: str | None = Field(default=None, max_length=MAX_FEEDBACK_LENGTH)
    internal_notes: str | None = Field(default=None, max_length=MAX_NOTES_LENGTH)


class ReviseRequest(_Strict):
    reason: str = Field(min_length=3, max_length=MAX_REASON_LENGTH)


class ReviewOut(BaseModel):
    id: uuid.UUID
    status: str
    rubric_id: uuid.UUID
    rubric_version: int | None = None
    grader_id: uuid.UUID
    criterion_scores: dict[str, str]
    criterion_total: float | None
    reported_score: float | None
    is_provisional: bool
    feedback: str | None
    internal_notes: str | None
    revision_number: int
    supersedes_id: uuid.UUID | None
    revision_reason: str | None
    finalized_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QueueItemOut(BaseModel):
    attempt_id: uuid.UUID
    question_id: uuid.UUID
    test_id: uuid.UUID
    test_title: str
    section_name: str
    score_component: str
    # pending | draft | finalized (derived)
    status: str
    finished_at: datetime | None
    reported_score: float | None = None


class SubmissionDetailOut(BaseModel):
    attempt_id: uuid.UUID
    question_id: uuid.UUID
    test_title: str
    section_name: str
    score_component: str
    question_text: str
    question_type: str
    # The student's stored response; None when left blank. Speaking
    # responses are the stored text — audio capture does not exist yet.
    response_text: str | None
    status: str
    rubric: RubricOut | None
    reviews: list[ReviewOut]
