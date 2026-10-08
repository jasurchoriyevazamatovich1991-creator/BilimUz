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
    # Sprint 70 — additive. The student's submitted free-text answer for
    # short_answer/essay questions (Answer.text_answer, Sprint 45/66).
    # None both when unanswered and for choice-based question types
    # (which never populate Answer.text_answer). short_answer/essay are
    # never auto-graded (see AUTO_GRADABLE_QUESTION_TYPES), so is_correct
    # stays None for them even when answered — this field is what lets a
    # consumer tell "answered, not auto-graded" apart from "unanswered".
    text_answer: str | None
    # Sprint 80 — additive, all default None. Mirrors Sprint 77's
    # identical QuestionForAttemptOut.group_id/group_title/stimulus_text
    # fields exactly (attempts/schemas.py) — same reasoning applies here:
    # Result Review had no way to show a grouped question's shared
    # stimulus/passage at all before this sprint (confirmed by audit —
    # ResultService never fetched QuestionGroup data). None for every
    # question that has no group (all pre-Sprint-80 results, unchanged),
    # and also None when the referenced group has been soft-deleted —
    # same "deleted group looks exactly like no group" convention as
    # Sprint 77, not a dangling reference.
    group_id: uuid.UUID | None = None
    group_title: str | None = None
    stimulus_text: str | None = None


class ResultSectionOut(BaseModel):
    """Sprint 55 — read-only exposure of Sprint 54's ResultSection rows.
    Deliberately exposes only the fields a result consumer needs
    (id, section_id, raw_score, scaled_score) — no result_id (redundant,
    the client already has it from the enclosing ResultDetailOut),
    no timestamps/deleted_at (internal bookkeeping, not part of any
    other *Out schema's public shape in this module either).

    Sprint 73 — RS-FE-1. Added `name`/`order_number` (additive,
    both nullable). Sprint 72's audit found this backend data had NO
    frontend type or rendering at all, despite Sprint 72 itself having
    just fixed the underlying scoring correctness (RS-1) — a section id
    alone is useless for a human-readable result page, so the owning
    ExamSection's display name/order travel with it. Nullable because
    ResultSection rows can theoretically outlive their ExamSection row
    (no FK-cascade guarantee was ever established for this pair) —
    ResultService._get_result_sections() populates them from a live
    lookup and leaves them None if the section can't be found, same
    defensive posture as its existing section_repo-is-None fallback."""
    id: uuid.UUID
    section_id: uuid.UUID
    name: str | None = None
    order_number: int | None = None
    raw_score: float | None
    scaled_score: float | None

    model_config = {"from_attributes": True}


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
    # Sprint 55 — additive. Empty list for a non-modular result (every
    # result created before this sprint, and any result for a Test with
    # zero ExamSection rows) — existing clients that don't read this
    # field are completely unaffected; ResultOut (used by
    # GET /results/me's list view) is untouched, so that contract
    # doesn't change at all.
    sections: list[ResultSectionOut] = []


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
