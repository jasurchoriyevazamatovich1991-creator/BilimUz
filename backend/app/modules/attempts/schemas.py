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
    # Sprint 30 — additive, for multiple_choice questions only. A
    # request should set exactly one of selected_option/selected_options
    # depending on the question's question_type (enforced in the
    # service, not here — this schema stays a plain, permissive DTO
    # matching the existing style).
    selected_options: list[uuid.UUID] | None = None
    # Sprint 66 — additive, for short_answer/essay questions only. Free
    # text the student submits for a question type that cannot be
    # automatically graded. Persisted verbatim via the existing
    # AnswerRepository.upsert() path (Answer.text_answer, present since
    # Sprint 45); is_correct is left NULL for these until a future
    # manual-grading feature exists — see scoring.py's
    # AUTO_GRADABLE_QUESTION_TYPES for how this is kept out of the
    # automatic scoring denominator. Like selected_option(s) above, this
    # schema stays a plain, permissive DTO — which field is expected is
    # decided by question_type in the service, not here.
    #
    # Sprint 73 — VAL-1. Previously unbounded — a malicious or buggy
    # client could submit an arbitrarily large string, bloating Answer
    # storage with no application-level limit (no essay realistically
    # needs more than a few thousand characters; 10,000 is a generous
    # ceiling matching a long multi-paragraph essay with headroom).
    text_answer: str | None = Field(default=None, max_length=10_000)


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
    selected_options: list[uuid.UUID] | None = None
    # Sprint 68 — additive. Discovered during Sprint 68's frontend
    # implementation: text_answer was persisted since Sprint 66 but was
    # never returned by get_attempt_detail(), making resume of a
    # short_answer/essay answer technically impossible for the student
    # UI (the value existed in the DB but never reached the client).
    # Mirrors selected_option/selected_options exactly: null unless this
    # question is short_answer/essay AND an Answer row exists for it.
    # Does not touch scoring, AUTO_GRADABLE_QUESTION_TYPES, or any
    # denominator logic.
    text_answer: str | None = None


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
    # Sprint A (post-75, generic modular student exam UI groundwork) —
    # additive, defaults are impossible to omit by construction (always
    # explicitly set by get_attempt_detail()) but behave as None for
    # every attempt this previously existed for: a non-modular attempt
    # (module_execution_service not configured) or a modular attempt
    # with no currently-active AttemptModuleProgress row (e.g. the whole
    # exam is already finished). The id of the module currently being
    # delivered, when there is one — lets the student frontend know
    # "which module am I in" without guessing, then look up that
    # module's name/section via GET /attempts/{id}/modules/{module_id}
    # below. Never populated for a module the student hasn't been
    # routed to yet.
    module_id: uuid.UUID | None = None
    # Sprint 76 — additive. Audit finding (Phase 2/14): the real,
    # per-attempt deadline for the active module
    # (AttemptModuleProgress.expires_at — set once in
    # ModuleExecutionService._create_module_progress from the module's
    # own `duration`, independent of the whole-attempt
    # TestAttempt.expires_at) was computed and enforced server-side
    # since Sprint 50, but never serialized anywhere a student could
    # read it — ModuleForAttemptOut (Sprint A) intentionally only
    # exposes static ExamModule configuration (name/order/duration), not
    # this per-attempt instance value. Without it, a frontend module
    # timer would have no authoritative deadline to count down to. None
    # whenever module_id above is None (non-modular attempt, or no
    # active module right now), and also None for an active module that
    # was created with no `duration` (module.duration is None) — both
    # pre-existing, unchanged states.
    module_expires_at: datetime | None = None


class ModuleForAttemptOut(BaseModel):
    """Sprint A (post-75) — student-scoped module/section metadata, for
    building a module navigator UI. Deliberately a narrow read view:
    excludes difficulty_tier/routing_group/routing_variant (admin-only
    routing configuration surfaced by tests/router.py's Admin/Super
    Admin-only exam-modules endpoints — not something a student needs
    or should see). Only reachable for a module the attempt has
    actually been routed to (see AttemptService.get_module_for_attempt's
    IDOR guard) — a student can never discover an upcoming, unrouted
    module's existence through this endpoint."""
    id: uuid.UUID
    name: str
    order_number: int
    duration: int | None
    section_id: uuid.UUID
    section_name: str
    section_order_number: int

    model_config = {"from_attributes": True}


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


class SubmitModuleResultOut(BaseModel):
    """Sprint 50 — response for POST /attempts/{id}/modules/{module_id}/submit.
    result is populated ONLY when completed is True (the submitted
    module was the exam's last one) — mirrors SubmitResultOut's own
    "never leak result data early" rule from the whole-attempt flow."""
    completed: bool
    next_module_id: uuid.UUID | None
    result: SubmitResultOut | None
