"""
Pydantic v2 request/response contracts for the attempts module.
Two question-view schemas are the most important design decision here:
QuestionForAttemptOut (NEVER includes is_correct) vs. the questions
module's QuestionOut (authoring view, includes it) — never interchanged.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class StartAttemptRequest(BaseModel):
    test_id: uuid.UUID


class SaveAnswerRequest(BaseModel):
    question_id: uuid.UUID
    selected_option: uuid.UUID | None = None


class OptionForAttemptOut(BaseModel):
    """Deliberately excludes is_correct."""
    id: uuid.UUID
    option_text: str

    model_config = {"from_attributes": True}


class QuestionForAttemptOut(BaseModel):
    """Deliberately excludes is_correct (on options) and explanation —
    the student-facing, answer-hidden view. Never reuse
    questions.schemas.QuestionOut for this endpoint."""
    id: uuid.UUID
    question_text: str
    question_type: str
    score: float
    options: list[OptionForAttemptOut] = []

    model_config = {"from_attributes": True}


class AnsweredQuestionState(BaseModel):
    question_id: uuid.UUID
    is_answered: bool
    selected_option: uuid.UUID | None = None


class AttemptOut(BaseModel):
    id: uuid.UUID
    test_id: uuid.UUID
    status: str
    start_time: datetime
    expires_at: datetime | None
    finish_time: datetime | None

    model_config = {"from_attributes": True}


class AttemptDetailOut(AttemptOut):
    """Full state for the active test-taking screen: questions in the
    persisted (possibly randomized) order, plus which are already
    answered — but never which answer is correct."""
    questions: list[QuestionForAttemptOut]
    answered: list[AnsweredQuestionState]


class SubmitResultOut(BaseModel):
    attempt_id: uuid.UUID
    score: float
    percentage: float
    is_passed: bool | None  # None if the test has no passing_score set
    total_questions: int
    correct_count: int
    status: str


class AttemptListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    test_id: uuid.UUID | None = None
    status: str | None = None
