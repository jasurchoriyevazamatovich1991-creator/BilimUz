"""Pydantic v2 request/response contracts for the tests module."""
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.questions.validators import sanitize_rich_text
from app.modules.tests.validators import validate_duration, validate_passing_score, validate_test_title


class TestCreateRequest(BaseModel):
    subject_id: uuid.UUID | None = None
    grade_id: uuid.UUID | None = None
    topic_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    difficulty: str = "medium"
    # Mock-test entitlements spec §3 — "the teacher/admin must specify
    # its duration before publishing it." No default anymore (was 60):
    # every caller must now pass an explicit value. The frontend form
    # already always sends one (TestFormPage.tsx's own useState(60)),
    # so this is a pure server-side tightening, not a breaking UI change.
    duration: int
    passing_score: float | None = None
    shuffle_questions: bool = True
    shuffle_answers: bool = True
    # Sprint 45 — optional. None (the default) keeps the exact existing
    # behavior (platform default DEFAULT_MAX_ATTEMPTS = 1).
    max_attempts: int | None = None
    # Sprint 47 — optional, generic. No IELTS-specific enum.
    exam_variant: str | None = None
    # Mock-test entitlements spec §1/§2 — False for every test unless
    # explicitly opted in. True requires subject_id to also be set
    # (enforced below AND by ck_tests_mock_test_requires_subject) —
    # subject_id is the "direction" (a school subject OR an exam like
    # IELTS/SAT/GRE, both just rows in the existing, generic Subject
    # table) the entitlements module checks access against.
    is_mock_test: bool = False

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

    @model_validator(mode="after")
    def _mock_test_requires_subject(self) -> "TestCreateRequest":
        """Fast, fail-at-the-door copy of ck_tests_mock_test_requires_subject
        — a full create request always has both fields in scope, unlike
        a partial update (see TestService._validate_mock_test_consistency
        for why that case is handled in the service layer instead)."""
        if self.is_mock_test and self.subject_id is None:
            raise ValueError("is_mock_test=true uchun subject_id (fan/yo'nalish) ko'rsatilishi shart")
        return self


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
    is_mock_test: bool | None = None

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
    is_mock_test: bool
    # Task 4 — 'ielts' | 'sat' | 'gre' | None (plain percentage scoring).
    scoring_profile: str | None = None
    # Task 7 — IELTS 'academic' | 'general_training' | None.
    ielts_module: str | None = None
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
    # Task 4 — e.g. 'sat_math'; must belong to the test's scoring_profile.
    score_component: str | None = None
    # Task 6 — offer the on-screen calculator for this section (default off).
    calculator_enabled: bool = False


class ExamSectionUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    order_number: int | None = Field(default=None, ge=0)
    duration: int | None = Field(default=None, gt=0)
    score_component: str | None = None
    calculator_enabled: bool | None = None


class ExamSectionOut(BaseModel):
    id: uuid.UUID
    test_id: uuid.UUID
    name: str
    order_number: int
    duration: int | None
    score_component: str | None = None
    calculator_enabled: bool = False
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


# --- Sprint 53: QuestionGroup / Stimulus Admin CRUD ---

class QuestionGroupCreateRequest(BaseModel):
    test_id: uuid.UUID
    module_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    stimulus_text: str | None = None
    order_number: int = Field(default=0, ge=0)

    @field_validator("stimulus_text")
    @classmethod
    def _stimulus_text(cls, v: str | None) -> str | None:
        # Sprint 80 — audit found stimulus_text had NO sanitization at
        # all (unlike question_text/option_text since Sprint 32, and
        # explanation since Sprint 32's own dedicated fix). Rendered to
        # students during exam-taking (AttemptPage) and result review
        # (ResultPage) via FormulaText/dangerouslySetInnerHTML as of
        # this sprint — the exact same gap class explanation was fixed
        # for, now closed the same way: reuse sanitize_rich_text(), no
        # new dependency or allowlist.
        return sanitize_rich_text(v) if v else v


class QuestionGroupUpdateRequest(BaseModel):
    # test_id is deliberately NOT here — a group can never be moved to
    # another test through PATCH (Sprint 53's explicit rule).
    module_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    stimulus_text: str | None = None
    order_number: int | None = Field(default=None, ge=0)

    @field_validator("stimulus_text")
    @classmethod
    def _stimulus_text(cls, v: str | None) -> str | None:
        # Sprint 80 — see QuestionGroupCreateRequest._stimulus_text above.
        return sanitize_rich_text(v) if v else v


class QuestionGroupMediaCreateRequest(BaseModel):
    """Task 3 — attach an existing, finalized Upload to a group. The
    media_type is NOT accepted from the client: it is taken from the
    Upload's own file_type on the server."""
    upload_id: uuid.UUID


class QuestionGroupMediaOut(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    upload_id: uuid.UUID
    media_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class QuestionGroupOut(BaseModel):
    id: uuid.UUID
    test_id: uuid.UUID
    module_id: uuid.UUID | None
    title: str
    stimulus_text: str | None
    order_number: int
    # Task 3 — the group's active media (Admin/Super Admin endpoints only).
    media: list[QuestionGroupMediaOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Sprint 75 completion: RoutingThresholdRule Admin CRUD ---
# Persistence for adaptive_routing.PerformanceThresholdRule
# (attempts/adaptive_routing.py, Sprint 49), mirroring that dataclass's
# two fields (min_ratio, variant) exactly, plus the mandatory test_id
# scoping and the routing_group key RoutingThresholdRuleRepository
# groups by. Deliberately generic — no IELTS/GRE/SAT-specific field or
# enum anywhere in this schema.

class RoutingThresholdRuleCreateRequest(BaseModel):
    test_id: uuid.UUID
    routing_group: str = Field(min_length=1, max_length=50)
    min_ratio: float = Field(ge=0, le=1)
    variant: str = Field(min_length=1, max_length=50)


class RoutingThresholdRuleUpdateRequest(BaseModel):
    # test_id is deliberately NOT here — mirrors QuestionGroupUpdateRequest's
    # own rule: a rule can never be moved to another test through PATCH.
    routing_group: str | None = Field(default=None, min_length=1, max_length=50)
    min_ratio: float | None = Field(default=None, ge=0, le=1)
    variant: str | None = Field(default=None, min_length=1, max_length=50)


class RoutingThresholdRuleOut(BaseModel):
    id: uuid.UUID
    test_id: uuid.UUID
    routing_group: str
    min_ratio: float
    variant: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Task 4: exam-specific scaled scoring (Admin/Super Admin only) ---

class ScoringProfileUpdateRequest(BaseModel):
    """null switches the test back to plain percentage scoring.

    Task 7 — ielts_module ('academic' | 'general_training') applies to the
    IELTS profile only. Omitted = keep the current value (when the profile
    stays IELTS); it is cleared automatically for any other profile."""
    scoring_profile: str | None = None
    ielts_module: str | None = None


class ConversionTableEntryIn(BaseModel):
    """'exact'/'linear': raw + scaled. Task 7 'range': raw + lower + upper."""
    raw: Decimal
    scaled: Decimal | None = None
    lower: Decimal | None = None
    upper: Decimal | None = None


class ConversionTableCreateRequest(BaseModel):
    """Publishes a NEW version; existing versions are never modified.

    Task 7 — provenance. conversion_type 'official_practice_test' needs a
    registered test_form (SAT Practice Test 4–11); its source URL/title come
    from the registry, not from the request. 'estimate' and 'unverified'
    may carry a free-form source description."""
    routing_variant: str | None = Field(default=None, min_length=1, max_length=50)
    method: str = "exact"
    # Required for every type except 'official_practice_test', whose values
    # always come from the verified dataset (Task 8; if sent they must match).
    entries: list[ConversionTableEntryIn] = Field(default_factory=list, max_length=500)
    conversion_type: str = "unverified"
    test_form: str | None = Field(default=None, max_length=60)
    source_url: str | None = Field(default=None, max_length=500)
    source_title: str | None = Field(default=None, max_length=300)
    source_version: str | None = Field(default=None, max_length=100)
    source_verified_at: date | None = None




class ConversionTableOut(BaseModel):
    id: uuid.UUID
    section_id: uuid.UUID
    routing_variant: str | None
    version: int
    method: str
    # As stored: {"raw", "scaled"} for exact/linear, {"raw", "lower",
    # "upper"} for Task 7 'range' tables (exact decimal strings).
    entries: list[dict[str, str]]
    # Task 7 — provenance ('unverified' for every pre-0028 table).
    conversion_type: str = "unverified"
    test_form: str | None = None
    source_url: str | None = None
    source_title: str | None = None
    source_version: str | None = None
    source_verified_at: date | None = None
    # Task 8 — documented anomalies of the official source (warnings).
    source_anomalies: list[str] = []
    # True for the highest version of its (section, routing_variant) —
    # the one new results are scored with.
    is_current: bool = False
    created_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
