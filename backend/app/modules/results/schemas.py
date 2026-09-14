"""Pydantic v2 request/response contracts for the results module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.results.validators import validate_ranking_period


class CreateResultRequest(BaseModel):
    attempt_id: uuid.UUID


class ResultOut(BaseModel):
    id: uuid.UUID
    attempt_id: uuid.UUID
    user_id: uuid.UUID
    test_id: uuid.UUID
    score: float
    percentage: float
    is_passed: bool | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Sprint 37: Result Analysis ---
# Additive only — ResultOut above is completely unchanged, so every
# existing consumer (list_my_results / GET /results/me) keeps working
# exactly as before. ResultDetailOut is used ONLY by the single-result
# GET /results/{id} endpoint.

class OptionReviewOut(BaseModel):
    id: uuid.UUID
    option_text: str
    is_correct: bool


class QuestionReviewOut(BaseModel):
    question_id: uuid.UUID
    question_text: str
    question_type: str
    explanation: str | None
    options: list[OptionReviewOut]
    selected_option: uuid.UUID | None
    selected_options: list[uuid.UUID] | None
    # None means unanswered — mirrors Answer.is_correct's own
    # None-for-unanswered convention (attempts/service.py), not a
    # separate "unanswered" flag.
    is_correct: bool | None


class ResultDetailOut(ResultOut):
    total_questions: int
    correct_answers: int
    incorrect_answers: int
    unanswered: int
    # None only if finish_time is missing on the underlying attempt
    # (should not happen for a finished attempt in practice, but
    # historical/edge-case data is handled safely rather than assumed).
    time_spent_seconds: int | None
    questions: list[QuestionReviewOut]


class ResultListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    test_id: uuid.UUID | None = None
    sort: str = "-created_at"


class RankingRecomputeRequest(BaseModel):
    subject_id: uuid.UUID | None = None
    period: str = "all_time"

    @field_validator("period")
    @classmethod
    def _period(cls, v: str) -> str:
        return validate_ranking_period(v)


class RankingRecomputeResponse(BaseModel):
    subject_id: uuid.UUID | None
    period: str
    ranked_count: int
