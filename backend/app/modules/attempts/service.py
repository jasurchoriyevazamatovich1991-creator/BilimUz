"""
Business logic for the Test Engine's attempt lifecycle — start, save
answer, submit, lazy auto-finish, resume, result. See
docs/Sprint6_TestEngine_Architecture.md for the full design rationale
behind every decision referenced in the comments below.

Reads (never writes to) TestRepository, QuestionRepository, and
OptionRepository — all read-only, unmodified except for the one additive
method (QuestionRepository.list_all_for_test) documented in the
questions module's git history for this sprint.
"""
import uuid
from datetime import datetime, timezone

from app.core.audit import log_action
from app.modules.attempts.exceptions import (
    AttemptNotActiveException,
    AttemptNotFoundException,
    InvalidOptionReferenceException,
    InvalidQuestionReferenceException,
    MaxAttemptsExceededException,
    ResultNotAvailableException,
    TestNotPublishedException,
)
from app.modules.attempts.constants import ACTIVE_STATUSES, DEFAULT_MAX_ATTEMPTS
from app.modules.attempts.models import AttemptStatus, TestAttempt
from app.modules.attempts.repository import AnswerRepository, AttemptRepository
from app.modules.attempts.scoring import DEFAULT_SCORING_STRATEGY
from app.modules.attempts.schemas import (
    AnsweredQuestionState,
    AttemptDetailOut,
    AttemptListParams,
    AttemptOut,
    OptionForAttemptOut,
    QuestionForAttemptOut,
    SubmitResultOut,
)
from app.modules.attempts.validators import build_question_order, compute_expiry, is_expired
from app.modules.questions.repository import OptionRepository, QuestionRepository
from app.modules.tests.repository import TestRepository


class AttemptService:
    def __init__(
        self,
        repository: AttemptRepository,
        answer_repository: AnswerRepository,
        test_repository: TestRepository,
        question_repository: QuestionRepository,
        option_repository: OptionRepository,
        module_execution_service: "ModuleExecutionService | None" = None,
        module_repository: "ExamModuleRepository | None" = None,
    ):
        self.repo = repository
        self.answer_repo = answer_repository
        self.test_repo = test_repository
        self.question_repo = question_repository
        self.option_repo = option_repository
        # Sprint 50 — both optional, default None. Every existing
        # caller (all pre-Sprint-50 tests, and any future caller that
        # doesn't need module execution) that constructs AttemptService
        # with only the original 5 arguments is completely unaffected —
        # module_execution/is_modular_test() below is the only place
        # that ever reads these, and it degrades to the exact legacy
        # (non-modular) behavior when they're None.
        self.module_execution = module_execution_service
        self.module_repo = module_repository

    # --- Start ---------------------------------------------------------

    def start_attempt(self, test_id: uuid.UUID, user_id: uuid.UUID) -> TestAttempt:
        test = self.test_repo.get_by_id(test_id)
        if test is None:
            raise TestNotPublishedException("Test topilmadi yoki e'lon qilinmagan")
        if test.status != "published":
            raise TestNotPublishedException("Faqat e'lon qilingan testlarga urinish boshlash mumkin")

        # Sprint 45 — test.max_attempts (nullable) overrides the
        # platform default when a Test opts in; every existing test has
        # max_attempts = NULL, so this is byte-identical behavior to
        # before this sprint for all of them.
        effective_max_attempts = test.max_attempts if test.max_attempts is not None else DEFAULT_MAX_ATTEMPTS
        existing = self.repo.count_for_user_and_test(user_id, test_id)
        if existing >= effective_max_attempts:
            raise MaxAttemptsExceededException(f"Bu test uchun maksimal urinishlar soni ({effective_max_attempts}) tugagan")

        questions = self.question_repo.list_all_for_test(test_id)
        question_ids = build_question_order([q.id for q in questions], shuffle=test.shuffle_questions)

        now = datetime.now(timezone.utc)
        attempt = TestAttempt(
            user_id=user_id, test_id=test_id, start_time=now,
            expires_at=compute_expiry(now, test.duration),
            question_order=question_ids, status=AttemptStatus.IN_PROGRESS,
        )
        self.repo.create(attempt)

        # Sprint 50 — the ONLY branch point in this method. A Test with
        # zero ExamModule rows (every existing Physics/generic test)
        # never reaches this block's body: has_modules() returns False,
        # and self.module_repo/self.module_execution being None (the
        # legacy AttemptService construction) short-circuits the same
        # way. TestAttempt.question_order above is still populated
        # exactly as before regardless — existing endpoints/tests that
        # read it are unaffected either way.
        if self.module_repo is not None and self.module_execution is not None and self.module_repo.has_modules(test_id):
            self.module_execution.initialize_first_module(attempt)

        log_action(self.repo.db, action="attempt.started", user_id=user_id, entity_type="test_attempt", entity_id=attempt.id)
        self.repo.commit()
        return attempt

    # --- Resume / view ---------------------------------------------------

    def get_attempt(self, attempt_id: uuid.UUID, user_id: uuid.UUID) -> TestAttempt:
        attempt = self._get_owned_attempt(attempt_id, user_id)
        self._auto_finish_if_expired(attempt)
        return attempt

    def get_attempt_detail(self, attempt_id: uuid.UUID, user_id: uuid.UUID) -> AttemptDetailOut:
        attempt = self.get_attempt(attempt_id, user_id)

        # Sprint 57 — question DELIVERY now follows the same
        # active-module boundary that save_answer() already enforces via
        # validate_question_in_module() (see below). Before this fix,
        # this method always used the whole-test attempt.question_order
        # regardless of which module was active, so a modular attempt
        # leaked every future module's question content immediately
        # after start_attempt. Non-modular attempts (module_execution is
        # None) and the same edge case save_answer() already tolerates
        # (module execution configured but no active AttemptModuleProgress
        # row right now) are completely unaffected — both fall through to
        # the original attempt.question_order behavior, unchanged.
        effective_question_order = attempt.question_order or []
        if self.module_execution is not None:
            active_progress = self.module_execution.get_active_module_progress(attempt_id)
            if active_progress is not None:
                effective_question_order = active_progress.question_order or []

        questions = [self.question_repo.get_by_id(qid) for qid in effective_question_order]
        answers = {a.question_id: a for a in self.answer_repo.list_for_attempt(attempt_id)}

        question_views = [self._to_question_view(q) for q in questions if q is not None]
        answered_states = [
            AnsweredQuestionState(
                question_id=qid, is_answered=qid in answers,
                selected_option=answers[qid].selected_option if qid in answers else None,
                selected_options=answers[qid].selected_options if qid in answers else None,
            )
            for qid in effective_question_order
        ]
        return AttemptDetailOut(**AttemptOut.model_validate(attempt).model_dump(), questions=question_views, answered=answered_states)

    def list_my_attempts(self, user_id: uuid.UUID, params: AttemptListParams) -> tuple[list[TestAttempt], int]:
        return self.repo.list_for_user(user_id, params)

    # --- Answer ------------------------------------------------------------

    def save_answer(
        self, attempt_id: uuid.UUID, user_id: uuid.UUID, question_id: uuid.UUID,
        selected_option: uuid.UUID | None, selected_options: list[uuid.UUID] | None = None,
    ) -> None:
        attempt = self._get_owned_attempt(attempt_id, user_id)
        self._auto_finish_if_expired(attempt)
        if attempt.status not in ACTIVE_STATUSES:
            raise AttemptNotActiveException("Bu urinish allaqachon yakunlangan")
        if question_id not in (attempt.question_order or []):
            raise InvalidQuestionReferenceException("Bu savol ushbu urinishga tegishli emas")

        # Sprint 50 — additional, module-scoped validation. A complete
        # no-op for non-modular attempts (self.module_execution is None,
        # or this attempt simply has no active module progress row —
        # the legacy TestAttempt.question_order check above already
        # covers everything for those).
        if self.module_execution is not None:
            active_progress = self.module_execution.get_active_module_progress(attempt_id)
            if active_progress is not None:
                self.module_execution.validate_question_in_module(active_progress, question_id)

        question = self.question_repo.get_by_id(question_id)
        if question is not None and question.question_type == "multiple_choice":
            # Sprint 30 — the only new branch. single_choice/true_false
            # below is byte-for-byte the original Sprint 6 logic.
            is_correct = self._check_options(question_id, selected_options or [])
            # Sprint 58 — a single atomic upsert replaces the old
            # get()-then-create()/update() check-then-act. The old code
            # had no path that expected the losing side's INSERT to be
            # rejected by uq_answers_attempt_question — a UNIQUE
            # constraint on (attempt_id, question_id) that has existed
            # in the database since migration 0001 (never a new
            # migration for this sprint; see AnswerRepository.upsert()).
            self.answer_repo.upsert(attempt_id, question_id, {"selected_options": selected_options, "selected_option": None, "is_correct": is_correct})
            self.repo.commit()
            return

        is_correct = self._check_option(question_id, selected_option)
        self.answer_repo.upsert(attempt_id, question_id, {"selected_option": selected_option, "is_correct": is_correct})
        self.repo.commit()

    # --- Submit / result -----------------------------------------------------

    def submit_attempt(self, attempt_id: uuid.UUID, user_id: uuid.UUID) -> SubmitResultOut:
        attempt = self._get_owned_attempt(attempt_id, user_id)
        self._auto_finish_if_expired(attempt)
        if attempt.status not in ACTIVE_STATUSES:
            raise AttemptNotActiveException("Bu urinish allaqachon yakunlangan")

        self._finalize(attempt, AttemptStatus.SUBMITTED)
        log_action(self.repo.db, action="attempt.submitted", user_id=user_id, entity_type="test_attempt", entity_id=attempt_id)
        self.repo.commit()
        return self._build_result(attempt)

    def get_result(self, attempt_id: uuid.UUID, user_id: uuid.UUID) -> SubmitResultOut:
        attempt = self._get_owned_attempt(attempt_id, user_id)
        self._auto_finish_if_expired(attempt)
        if attempt.status in ACTIVE_STATUSES:
            raise ResultNotAvailableException("Urinish hali yakunlanmagan")
        return self._build_result(attempt)

    # --- Sprint 50: modular execution ---------------------------------

    def submit_module(self, attempt_id: uuid.UUID, module_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        """Requires self.module_execution to be configured (see
        get_attempt_service's Sprint 50 wiring) — this method has no
        meaning for a non-modular AttemptService construction and is
        never called for one (no router path reaches it without a
        module_id in the URL)."""
        attempt = self._get_owned_attempt(attempt_id, user_id)
        self._auto_finish_if_expired(attempt)
        if attempt.status not in ACTIVE_STATUSES:
            raise AttemptNotActiveException("Bu urinish allaqachon yakunlangan")

        progress = self.module_execution.get_owned_module_progress(attempt, module_id)
        outcome = self.module_execution.submit_module(attempt, progress)

        if outcome["completed"]:
            self._finalize(attempt, AttemptStatus.SUBMITTED)
            log_action(self.repo.db, action="attempt.submitted", user_id=user_id, entity_type="test_attempt", entity_id=attempt_id)
            self.repo.commit()
            result = self._build_result(attempt)
            return {"completed": True, "next_module_id": None, "result": result}

        self.repo.commit()
        return {"completed": False, "next_module_id": outcome["next_module_id"], "result": None}

    # --- Internal helpers --------------------------------------------------

    def _get_owned_attempt(self, attempt_id: uuid.UUID, user_id: uuid.UUID) -> TestAttempt:
        attempt = self.repo.get_by_id(attempt_id)
        if attempt is None or attempt.user_id != user_id:
            raise AttemptNotFoundException("Urinish topilmadi")
        return attempt

    def _check_option(self, question_id: uuid.UUID, selected_option: uuid.UUID | None) -> bool | None:
        if selected_option is None:
            return None
        option = self.option_repo.get_by_id(selected_option)
        if option is None or option.question_id != question_id:
            raise InvalidOptionReferenceException("Tanlangan variant bu savolga tegishli emas")
        return option.is_correct

    def _check_options(self, question_id: uuid.UUID, selected_options: list[uuid.UUID]) -> bool | None:
        """Sprint 30 — multiple_choice scoring. Correct iff the
        student's selected set is EXACTLY the set of correct options —
        every correct option chosen, and no incorrect one chosen
        (standard multi-select grading, not partial credit). Returns
        None (unanswered) only for a genuinely empty selection, mirroring
        _check_option's None-for-unanswered convention above."""
        if not selected_options:
            return None
        all_options = self.option_repo.list_for_question(question_id)
        valid_ids = {o.id for o in all_options}
        for option_id in selected_options:
            if option_id not in valid_ids:
                raise InvalidOptionReferenceException("Tanlangan variant bu savolga tegishli emas")
        correct_ids = {o.id for o in all_options if o.is_correct}
        return set(selected_options) == correct_ids

    def _auto_finish_if_expired(self, attempt: TestAttempt) -> None:
        """Lazy expiration — see docs/Sprint6_TestEngine_Architecture.md
        Section 6. Designed so a future Celery task could call _finalize()
        proactively without changing this method's public callers."""
        if attempt.status in ACTIVE_STATUSES and is_expired(attempt.expires_at):
            self._finalize(attempt, AttemptStatus.AUTO_FINISHED)
            self.repo.commit()

    def _finalize(self, attempt: TestAttempt, new_status: AttemptStatus) -> None:
        answers = self.answer_repo.list_for_attempt(attempt.id)
        questions = [self.question_repo.get_by_id(qid) for qid in (attempt.question_order or [])]
        questions = [q for q in questions if q is not None]

        # Sprint 45 — delegates to the Scoring Strategy foundation
        # (scoring.py). DEFAULT_SCORING_STRATEGY.calculate() is the
        # exact same arithmetic this method used to do inline —
        # extracted, not changed.
        result = DEFAULT_SCORING_STRATEGY.calculate(questions, answers)

        self.repo.update(attempt, {
            "status": new_status.value, "finish_time": datetime.now(timezone.utc),
            "score": result.score, "percentage": result.percentage,
        })

    def _build_result(self, attempt: TestAttempt) -> SubmitResultOut:
        test = self.test_repo.get_by_id(attempt.test_id)
        answers = self.answer_repo.list_for_attempt(attempt.id)
        correct_count = sum(1 for a in answers if a.is_correct is True)
        is_passed = None
        if test is not None and test.passing_score is not None and attempt.percentage is not None:
            is_passed = float(attempt.percentage) >= float(test.passing_score)

        return SubmitResultOut(
            attempt_id=attempt.id, score=float(attempt.score or 0), percentage=float(attempt.percentage or 0),
            is_passed=is_passed, total_questions=len(attempt.question_order or []),
            correct_count=correct_count, status=attempt.status,
        )

    def _to_question_view(self, question) -> QuestionForAttemptOut:
        options = [OptionForAttemptOut.model_validate(o) for o in question.options if o.deleted_at is None]
        return QuestionForAttemptOut(
            id=question.id, question_text=question.question_text,
            question_type=question.question_type, score=float(question.score), options=options,
        )
