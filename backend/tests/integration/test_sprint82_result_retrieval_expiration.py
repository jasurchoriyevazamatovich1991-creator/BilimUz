"""
Sprint 82 — Package 2 (Result Retrieval and Expiration), against real
PostgreSQL. Same construction style as test_module_execution.py (real
repositories via pg_session, not mocks) — the defect and fix both live
entirely in AttemptService.get_result()'s interaction with
ModuleExecutionService's real per-module expiry logic, which needs real
AttemptModuleProgress rows to exercise meaningfully.

Defect under test: AttemptService.get_result() called
self._auto_finish_if_expired(attempt) (whole-attempt expiry) but NOT
self._auto_finish_active_module_if_expired(attempt) (per-module expiry,
Sprint 79) — the one call every other attempt-lifecycle entry point
(get_attempt(), save_answer(), submit_attempt(), submit_module()) already
has. For a modular test whose active module's own (shorter) expires_at
has passed while the whole-attempt Test.duration/TestAttempt.expires_at
has NOT — the normal configuration for a modular test — calling
get_result() alone could never discover or act on that expiry: the
attempt stayed "in_progress" forever unless some OTHER endpoint
(e.g. GET /attempts/{id}) happened to be called first. A student whose
client only ever polls the result endpoint would see "natija hali
tayyor emas" (ResultNotAvailableException) indefinitely even though the
exact same attempt would have auto-finished correctly through
get_attempt_detail().

Fix: get_result() now also calls
self._auto_finish_active_module_if_expired(attempt), in the same
position every other entry point already calls it.
"""
import uuid
from datetime import datetime, timedelta, timezone

from app.modules.attempts.models import AttemptModuleProgress, AttemptStatus, TestAttempt
from app.modules.attempts.module_execution_service import ModuleExecutionService
from app.modules.attempts.repository import AnswerRepository, AttemptModuleProgressRepository, AttemptRepository
from app.modules.attempts.service import AttemptService
from app.modules.questions.models import Question, QuestionOption
from app.modules.questions.repository import OptionRepository, QuestionRepository
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import ExamModule, ExamSection, Test
from app.modules.tests.repository import ExamModuleRepository, TestRepository
from app.modules.users.models import User, UserStatus


def _make_student(pg_session) -> uuid.UUID:
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name="S82", last_name="R", email=f"s82r-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    pg_session.flush()
    return user.id


def _make_service(pg_session) -> AttemptService:
    return AttemptService(
        AttemptRepository(pg_session), AnswerRepository(pg_session), TestRepository(pg_session),
        QuestionRepository(pg_session), OptionRepository(pg_session),
        ModuleExecutionService(
            ExamModuleRepository(pg_session), AttemptModuleProgressRepository(pg_session),
            QuestionRepository(pg_session), AnswerRepository(pg_session), AttemptRepository(pg_session),
        ),
        ExamModuleRepository(pg_session),
    )


def _make_question_with_correct_option(pg_session, test_id, module_id=None) -> tuple[Question, QuestionOption]:
    q = Question(test_id=test_id, question_text="Q", question_type="single_choice", score=1, module_id=module_id)
    pg_session.add(q)
    pg_session.flush()
    correct = QuestionOption(question_id=q.id, option_text="A", is_correct=True)
    wrong = QuestionOption(question_id=q.id, option_text="B", is_correct=False)
    pg_session.add_all([correct, wrong])
    pg_session.flush()
    return q, correct


# --- scenario: active (not expired) — unchanged, still raises ---

def test_get_result_still_raises_while_genuinely_active(pg_session):
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Active Test", duration=30, question_count=1, status="published")
    pg_session.add(test)
    pg_session.flush()
    question, correct = _make_question_with_correct_option(pg_session, test.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    from app.modules.attempts.exceptions import ResultNotAvailableException
    import pytest
    with pytest.raises(ResultNotAvailableException):
        service.get_result(attempt.id, student_id)


# --- scenario: expired module, whole-attempt NOT expired — the core fix ---

def test_get_result_auto_finishes_expired_module_without_any_prior_get_attempt_call(pg_session):
    """The exact scenario the defect left permanently stuck: Test.duration
    far outlasts module.duration, and get_result() — never
    get_attempt()/get_attempt_detail() — is the ONLY endpoint ever
    called on this attempt after it expires. Before the fix, this raised
    ResultNotAvailableException forever. After the fix, get_result()
    itself notices the expired module, auto-finishes the (only, so
    whole-exam-completing) module, and returns the real result in the
    same call."""
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Modular Result Test", duration=600, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0, duration=10)
    pg_session.add(module1)
    pg_session.flush()
    question, correct = _make_question_with_correct_option(pg_session, test.id, module_id=module1.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()
    service.save_answer(attempt.id, student_id, question.id, selected_option=correct.id)
    pg_session.commit()

    # Force the module's own expiry into the past — the whole-attempt
    # Test.duration=600 has NOT expired, so only the module-level lazy
    # check (the one get_result() was missing) can recover this attempt.
    progress = pg_session.query(AttemptModuleProgress).filter(AttemptModuleProgress.attempt_id == attempt.id).one()
    progress.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    pg_session.commit()

    # get_result() — and ONLY get_result() — is called. No
    # get_attempt()/get_attempt_detail() call precedes it.
    result = service.get_result(attempt.id, student_id)
    pg_session.commit()

    assert result.status == AttemptStatus.AUTO_FINISHED.value
    assert result.correct_count == 1
    assert result.score == 1.0
    assert result.percentage == 100.0

    reloaded_attempt = pg_session.query(TestAttempt).filter(TestAttempt.id == attempt.id).one()
    assert reloaded_attempt.status == AttemptStatus.AUTO_FINISHED.value

    reloaded_progress = pg_session.query(AttemptModuleProgress).filter(AttemptModuleProgress.attempt_id == attempt.id).one()
    assert reloaded_progress.status == "submitted"
    assert reloaded_progress.submitted_at is not None


# --- scenario: completed (already submitted) — unaffected ---

def test_get_result_for_normally_completed_attempt_is_unaffected(pg_session):
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Normal Completion Test", duration=30, question_count=1, status="published")
    pg_session.add(test)
    pg_session.flush()
    question, correct = _make_question_with_correct_option(pg_session, test.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()
    service.save_answer(attempt.id, student_id, question.id, selected_option=correct.id)
    pg_session.commit()
    service.submit_attempt(attempt.id, student_id)
    pg_session.commit()

    result = service.get_result(attempt.id, student_id)
    assert result.status == AttemptStatus.SUBMITTED.value
    assert result.correct_count == 1


# --- scenario: repeated result requests are safe, no duplicate side effects ---

def test_repeated_get_result_calls_on_expired_module_are_idempotent(pg_session):
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Repeated Result Test", duration=600, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0, duration=10)
    pg_session.add(module1)
    pg_session.flush()
    question, correct = _make_question_with_correct_option(pg_session, test.id, module_id=module1.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()
    service.save_answer(attempt.id, student_id, question.id, selected_option=correct.id)
    pg_session.commit()

    progress = pg_session.query(AttemptModuleProgress).filter(AttemptModuleProgress.attempt_id == attempt.id).one()
    progress.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    pg_session.commit()

    first = service.get_result(attempt.id, student_id)
    pg_session.commit()
    second = service.get_result(attempt.id, student_id)
    pg_session.commit()
    third = service.get_result(attempt.id, student_id)
    pg_session.commit()

    for result in (first, second, third):
        assert result.status == AttemptStatus.AUTO_FINISHED.value
        assert result.score == 1.0
        assert result.percentage == 100.0
        assert result.correct_count == 1

    # No duplicate side effects: exactly one module-progress row,
    # submitted exactly once, and the score/percentage are stable
    # (re-finalizing would be a bug — _lock_attempt()'s re-check under
    # the lock is what prevents it).
    progress_rows = pg_session.query(AttemptModuleProgress).filter(AttemptModuleProgress.attempt_id == attempt.id).all()
    assert len(progress_rows) == 1
    assert progress_rows[0].status == "submitted"
