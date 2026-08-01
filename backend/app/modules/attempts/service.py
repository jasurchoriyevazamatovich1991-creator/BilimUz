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
from app.modules.attempts.models import Answer, AttemptStatus, TestAttempt
from app.modules.attempts.repository import AnswerRepository, AttemptRepository
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
    ):
        self.repo = repository
        self.answer_repo = answer_repository
        self.test_repo = test_repository
        self.question_repo = question_repository
        self.option_repo = option_repository

    # --- Start ---------------------------------------------------------

    def start_attempt(self, test_id: uuid.UUID, user_id: uuid.UUID) -> TestAttempt:
        test = self.test_repo.get_by_id(test_id)
        if test is None:
            raise TestNotPublishedException("Test topilmadi yoki e'lon qilinmagan")
        if test.status != "published":
            raise TestNotPublishedException("Faqat e'lon qilingan testlarga urinish boshlash mumkin")

        existing = self.repo.count_for_user_and_test(user_id, test_id)
        if existing >= DEFAULT_MAX_ATTEMPTS:
            raise MaxAttemptsExceededException(f"Bu test uchun maksimal urinishlar soni ({DEFAULT_MAX_ATTEMPTS}) tugagan")

        questions = self.question_repo.list_all_for_test(test_id)
        question_ids = build_question_order([q.id for q in questions], shuffle=test.shuffle_questions)

        now = datetime.now(timezone.utc)
        attempt = TestAttempt(
            user_id=user_id, test_id=test_id, start_time=now,
            expires_at=compute_expiry(now, test.duration),
            question_order=question_ids, status=AttemptStatus.IN_PROGRESS,
        )
        self.repo.create(attempt)
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
        questions = [self.question_repo.get_by_id(qid) for qid in (attempt.question_order or [])]
        answers = {a.question_id: a for a in self.answer_repo.list_for_attempt(attempt_id)}

        question_views = [self._to_question_view(q) for q in questions if q is not None]
        answered_states = [
            AnsweredQuestionState(
                question_id=qid, is_answered=qid in answers,
                selected_option=answers[qid].selected_option if qid in answers else None,
            )
            for qid in (attempt.question_order or [])
        ]
        return AttemptDetailOut(**AttemptOut.model_validate(attempt).model_dump(), questions=question_views, answered=answered_states)

    def list_my_attempts(self, user_id: uuid.UUID, params: AttemptListParams) -> tuple[list[TestAttempt], int]:
        return self.repo.list_for_user(user_id, params)

    # --- Answer ------------------------------------------------------------

    def save_answer(self, attempt_id: uuid.UUID, user_id: uuid.UUID, question_id: uuid.UUID, selected_option: uuid.UUID | None) -> None:
        attempt = self._get_owned_attempt(attempt_id, user_id)
        self._auto_finish_if_expired(attempt)
        if attempt.status not in ACTIVE_STATUSES:
            raise AttemptNotActiveException("Bu urinish allaqachon yakunlangan")
        if question_id not in (attempt.question_order or []):
            raise InvalidQuestionReferenceException("Bu savol ushbu urinishga tegishli emas")

        is_correct = self._check_option(question_id, selected_option)
        existing = self.answer_repo.get(attempt_id, question_id)
        if existing:
            self.answer_repo.update(existing, {"selected_option": selected_option, "is_correct": is_correct})
        else:
            self.answer_repo.create(Answer(attempt_id=attempt_id, question_id=question_id, selected_option=selected_option, is_correct=is_correct))
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

        correct_by_question = {a.question_id: a.is_correct for a in answers}
        total_score = sum(float(q.score) for q in questions if correct_by_question.get(q.id) is True)
        total_possible = sum(float(q.score) for q in questions) or 1.0
        percentage = round((total_score / total_possible) * 100, 2)

        self.repo.update(attempt, {
            "status": new_status.value, "finish_time": datetime.now(timezone.utc),
            "score": total_score, "percentage": percentage,
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
