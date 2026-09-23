"""
Sprint 50 — Generic Exam Execution Engine.

Connects the Sprint 45-49 foundation (ExamModule, AttemptModuleProgress,
ScoringStrategy, AdaptiveRoutingStrategy) to real attempt execution.

Kept as a SEPARATE service from AttemptService on purpose — this is the
new, module-execution-specific responsibility; AttemptService's existing,
already-tested legacy (non-modular) flow is left untouched except for
the smallest possible branch at start_attempt() (see attempts/service.py).

Backward compatibility is the hard requirement throughout this file: a
Test with zero ExamModule rows (every existing Physics/generic test)
never reaches any method here — AttemptService checks
ExamModuleRepository.has_modules() first and only calls into this
service when it's True.
"""
import uuid
from datetime import datetime, timedelta, timezone

from app.modules.attempts.adaptive_routing import ModuleCandidate, ModulePerformance, SequentialRoutingStrategy
from app.modules.attempts.exceptions import (
    InvalidQuestionReferenceException,
    ModuleNotActiveException,
    ModuleNotFoundForAttemptException,
)
from app.modules.attempts.models import AttemptModuleProgress, AttemptStatus, TestAttempt
from app.modules.attempts.repository import AnswerRepository, AttemptModuleProgressRepository, AttemptRepository
from app.modules.attempts.scoring import DEFAULT_SCORING_STRATEGY
from app.modules.attempts.validators import build_question_order
from app.modules.questions.repository import QuestionRepository
from app.modules.tests.repository import ExamModuleRepository


class ModuleExecutionService:
    def __init__(
        self,
        module_repo: ExamModuleRepository,
        progress_repo: AttemptModuleProgressRepository,
        question_repo: QuestionRepository,
        answer_repo: AnswerRepository,
        attempt_repo: AttemptRepository,
    ):
        self.module_repo = module_repo
        self.progress_repo = progress_repo
        self.question_repo = question_repo
        self.answer_repo = answer_repo
        self.attempt_repo = attempt_repo
        # Sprint 49's PerformanceThresholdRoutingStrategy needs
        # caller-supplied threshold rules this generic execution layer
        # has no exam-specific knowledge of (by design — see Sprint 49's
        # own "no exam-specific defaults" requirement). Until a future
        # sprint wires real per-exam configuration through, the
        # execution layer uses SequentialRoutingStrategy — itself a
        # real AdaptiveRoutingStrategy implementation Sprint 48 already
        # shipped, not a placeholder invented here.
        self.routing_strategy = SequentialRoutingStrategy()

    # --- Module initialization -------------------------------------------

    def initialize_first_module(self, attempt: TestAttempt) -> AttemptModuleProgress | None:
        """Called once, from AttemptService.start_attempt(), only when
        ExamModuleRepository.has_modules(test_id) is True. Returns None
        if there are genuinely no modules (defensive — the caller
        already checked, but this method never assumes).

        Respects ExamModule.order_number / ExamSection.order_number via
        ExamModuleRepository.list_for_test()'s own ordering — the first
        module in that order is where execution starts. No routing
        decision for the first module (Sprint 50's explicit
        requirement) — it's simply the first one."""
        modules = self.module_repo.list_for_test(attempt.test_id)
        if not modules:
            return None
        first_module = modules[0]
        return self._create_module_progress(attempt, first_module)

    def _create_module_progress(self, attempt: TestAttempt, module) -> AttemptModuleProgress:
        questions = self.question_repo.list_by_module(module.id)
        question_ids = build_question_order([q.id for q in questions], shuffle=False)
        # Module-level shuffle is deliberately not implemented this
        # sprint — Test.shuffle_questions is a whole-test setting with
        # no per-module equivalent yet; inventing one would be a new
        # generic feature beyond this sprint's connect-the-foundation
        # scope. question_ids is still a real, persisted snapshot.

        now = datetime.now(timezone.utc)
        expires_at = None
        if module.duration is not None:
            expires_at = now + timedelta(minutes=module.duration)
        # module.duration is None -> no module-level expiry is invented;
        # the whole-attempt Test.duration/TestAttempt.expires_at (set at
        # start_attempt(), untouched by this sprint) still applies.

        progress = AttemptModuleProgress(
            attempt_id=attempt.id, module_id=module.id, status=AttemptStatus.IN_PROGRESS.value,
            question_order=question_ids, expires_at=expires_at,
        )
        self.progress_repo.create(progress)
        return progress

    # --- Access / validation ----------------------------------------------

    def get_active_module_progress(self, attempt_id: uuid.UUID) -> AttemptModuleProgress | None:
        return self.progress_repo.get_active_for_attempt(attempt_id)

    def get_owned_module_progress(self, attempt: TestAttempt, module_id: uuid.UUID) -> AttemptModuleProgress:
        """The IDOR guard for module-scoped operations. A progress row
        that doesn't exist for THIS attempt (wrong module_id, or a
        module_id that belongs to some other student's attempt
        entirely) raises the identical exception either way — no
        signal about which case it was."""
        progress = self.progress_repo.get_for_attempt_and_module(attempt.id, module_id)
        if progress is None:
            raise ModuleNotFoundForAttemptException("Bu modul ushbu urinishga tegishli emas")
        return progress

    def validate_active(self, progress: AttemptModuleProgress) -> None:
        if progress.status != AttemptStatus.IN_PROGRESS.value or progress.submitted_at is not None:
            raise ModuleNotActiveException("Bu modul faol emas")
        if progress.expires_at is not None and progress.expires_at < datetime.now(timezone.utc):
            raise ModuleNotActiveException("Bu modul uchun vaqt tugagan")

    def validate_question_in_module(self, progress: AttemptModuleProgress, question_id: uuid.UUID) -> None:
        if question_id not in (progress.question_order or []):
            raise InvalidQuestionReferenceException("Bu savol ushbu modulga tegishli emas")

    # --- Submission / routing ----------------------------------------------

    def submit_module(self, attempt: TestAttempt, progress: AttemptModuleProgress) -> dict:
        """Returns {"completed": bool, "next_module_id": uuid.UUID | None}
        so the router/AttemptService caller knows whether to finalize
        the whole attempt or the client should move to the next module.

        Sprint 50 CRITICAL-1 fix: the very first thing this method does
        is re-acquire `progress` via a locked, populate_existing SELECT
        (get_for_attempt_and_module_locked) — a real PostgreSQL
        row-level lock on this exact (attempt_id, module_id) row. A
        second, concurrent call for the SAME row (two simultaneous
        submit requests) blocks on that SELECT until the first call's
        transaction commits and releases the lock; it then sees the
        post-commit, already-"submitted" status and validate_active()
        correctly rejects it — the existing duplicate-submit exception,
        now reliably triggered instead of both calls racing past the
        earlier unlocked check. The `progress` parameter passed in is
        deliberately only used for its module_id/attempt identity here;
        the locked re-fetch is the one whose attributes are trusted for
        every decision below.

        Transaction shape: everything from the lock acquisition through
        marking this module submitted, computing performance, the
        routing decision, and creating the next progress row (if any)
        happens against the same SQLAlchemy session/transaction without
        an intermediate commit — the caller (AttemptService) commits
        once at the end, which is also what releases this row lock."""
        locked_progress = self.progress_repo.get_for_attempt_and_module_locked(attempt.id, progress.module_id)
        self.validate_active(locked_progress)
        progress = locked_progress

        module = self.module_repo.get_by_id(progress.module_id)
        questions = self.question_repo.list_by_module(progress.module_id)
        answers = [a for a in self.answer_repo.list_for_attempt(attempt.id) if a.question_id in (progress.question_order or [])]

        # Sprint 45's ScoringStrategy, reused exactly — this is the
        # SAME generic percentage calculation AttemptService._finalize()
        # already uses for the whole-attempt case, applied here at
        # module scope instead.
        scoring_result = DEFAULT_SCORING_STRATEGY.calculate(questions, answers)
        correct_count = sum(1 for a in answers if a.is_correct is True)

        self.progress_repo.update(progress, {
            "status": AttemptStatus.SUBMITTED.value,
            "submitted_at": datetime.now(timezone.utc),
        })

        next_module_id = self._route_to_next_module(attempt, module, correct_count, len(questions))
        if next_module_id is None:
            return {"completed": True, "next_module_id": None}

        next_module = self.module_repo.get_by_id(next_module_id)
        self._create_module_progress(attempt, next_module)
        return {"completed": False, "next_module_id": next_module_id}

    def _route_to_next_module(self, attempt: TestAttempt, completed_module, correct_count: int, total_count: int) -> uuid.UUID | None:
        all_modules = self.module_repo.list_for_test(attempt.test_id)
        already_progressed_ids = {p.module_id for p in self.progress_repo.list_for_attempt(attempt.id)}

        # Eligibility: exclude modules already completed/submitted or
        # already started (Sprint 50's explicit eligibility rule) —
        # a module this attempt already has ANY progress row for
        # (submitted or in-progress) is never offered again.
        candidates = [
            ModuleCandidate(module_id=m.id, order_number=m.order_number, routing_group=m.routing_group, routing_variant=m.routing_variant)
            for m in all_modules
            if m.id not in already_progressed_ids
        ]

        if total_count <= 0:
            # No questions in this module — nothing to compute a ratio
            # from; treat as "no further routable performance signal",
            # fall through to the deterministic strategy's own
            # no-candidates/order-based behavior below via a 0-count
            # performance (SequentialRoutingStrategy ignores
            # performance entirely, so this is safe for the shipped
            # strategy; documented here for any future
            # performance-based strategy wired in later).
            performance = ModulePerformance(correct_count=0, total_count=1)
        else:
            performance = ModulePerformance(correct_count=correct_count, total_count=total_count)

        decision = self.routing_strategy.decide_next_module(completed_module, performance, candidates)
        return decision.next_module_id

    def get_effective_question_ids(self, attempt_id: uuid.UUID) -> list[uuid.UUID] | None:
        """Sprint 61 — S61-C. The set of questions actually DELIVERED to
        this student across every module they were ever routed into —
        the correct scoring/total_questions scope for a modular attempt,
        replacing the old whole-test TestAttempt.question_order snapshot
        that AttemptService._finalize()/_build_result() used to use
        unconditionally (see the Sprint 61 audit finding S61-C: that
        snapshot silently included questions from modules a student was
        routed away from, and any orphan module_id=NULL question,
        scoring both as permanently wrong).

        Built from the deduplicated, order-preserving union of every
        AttemptModuleProgress.question_order row this attempt has —
        i.e. every module a progress row was ever created for, whether
        still in_progress (e.g. the attempt is being finalized early by
        auto-finish-on-expiry mid-module) or already submitted. A module
        the student was routed away from, or never reached, never gets a
        progress row (see _route_to_next_module's already_progressed_ids
        exclusion and initialize_first_module/‌_create_module_progress,
        which only ever create one when the student is actually routed
        into that module) — so its questions are naturally excluded
        without any extra filtering. A question with module_id = NULL
        is, by the same construction, never a member of ANY module's
        question_order (list_by_module() only returns questions whose
        module_id matches), so it is likewise excluded automatically.

        Returns None — not an empty list — when this attempt has NO
        module-progress rows at all. That is the "no/empty module
        progress" edge case (Sprint 61 audit Section 4.F): rather than
        inventing a new product rule for it (e.g. scoring zero
        questions), the caller falls back to the original, safe,
        already-established whole-test attempt.question_order behavior
        — the exact same fallback a non-modular attempt already uses,
        since a non-modular attempt also has zero progress rows by
        construction."""
        progress_rows = self.progress_repo.list_for_attempt(attempt_id)
        if not progress_rows:
            return None

        seen: set[uuid.UUID] = set()
        ordered_ids: list[uuid.UUID] = []
        for progress in progress_rows:
            for question_id in (progress.question_order or []):
                if question_id not in seen:
                    seen.add(question_id)
                    ordered_ids.append(question_id)
        return ordered_ids

    def is_exam_complete(self, attempt: TestAttempt) -> bool:
        """True once every ExamModule for this test has a submitted
        AttemptModuleProgress row — the generic completion rule Sprint
        50 requires ('finish the exam only when the generic execution
        rules determine there are no remaining modules')."""
        all_modules = self.module_repo.list_for_test(attempt.test_id)
        progress_rows = self.progress_repo.list_for_attempt(attempt.id)
        submitted_module_ids = {p.module_id for p in progress_rows if p.status == AttemptStatus.SUBMITTED.value}
        return {m.id for m in all_modules} <= submitted_module_ids
