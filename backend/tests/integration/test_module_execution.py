"""
Sprint 50 — Generic Exam Execution Engine integration tests, against
real PostgreSQL (Sprint 40's infrastructure — pg_session,
TEST_DATABASE_URL).

Constructs AttemptService directly with real repositories (matching
this project's existing integration-test style — see
test_adaptive_routing_foundation.py) rather than through FastAPI's DI,
so both the legacy (non-modular) and new (modular) execution paths are
exercised against real DB constraints, not mocks.
"""
import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.modules.attempts.exceptions import (
    AttemptNotActiveException,
    InvalidQuestionReferenceException,
    ModuleNotActiveException,
    ModuleNotFoundForAttemptException,
)
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
    user = User(role_id=role.id, first_name="E", last_name="X", email=f"ex-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
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


# --- A: non-modular regression ---

def test_non_modular_test_unaffected_by_sprint_50(pg_session):
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Plain Test", duration=30, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    q, correct = _make_question_with_correct_option(pg_session, test.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    # No AttemptModuleProgress created for a moduleless test.
    progress_rows = pg_session.query(AttemptModuleProgress).filter(AttemptModuleProgress.attempt_id == attempt.id).all()
    assert progress_rows == []

    service.save_answer(attempt.id, student_id, q.id, selected_option=correct.id)
    pg_session.commit()
    result = service.submit_attempt(attempt.id, student_id)
    pg_session.commit()
    assert result.status == "submitted"
    assert result.correct_count == 1


# --- B/C: modular start, question_order snapshot, module duration/expires_at ---

def test_modular_start_creates_first_module_progress(pg_session):
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Modular Test", duration=60, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0, duration=10)
    module2 = ExamModule(section_id=section.id, name="Module 2", order_number=1)
    pg_session.add_all([module1, module2])
    pg_session.flush()
    q1, _ = _make_question_with_correct_option(pg_session, test.id, module_id=module1.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    progress_rows = pg_session.query(AttemptModuleProgress).filter(AttemptModuleProgress.attempt_id == attempt.id).all()
    assert len(progress_rows) == 1
    progress = progress_rows[0]
    assert progress.module_id == module1.id
    assert progress.question_order == [q1.id]
    assert progress.status == "in_progress"
    assert progress.expires_at is not None  # module1.duration=10 -> expiry computed


def test_modular_start_module_without_duration_has_no_expires_at(pg_session):
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Modular Test No Duration", duration=60, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    pg_session.add(module1)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    progress = pg_session.query(AttemptModuleProgress).filter(AttemptModuleProgress.attempt_id == attempt.id).one()
    assert progress.expires_at is None


# --- D: module answer validation ---

def test_answer_from_another_module_rejected(pg_session):
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Modular Test", duration=60, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    module2 = ExamModule(section_id=section.id, name="Module 2", order_number=1)
    pg_session.add_all([module1, module2])
    pg_session.flush()
    q1, opt1 = _make_question_with_correct_option(pg_session, test.id, module_id=module1.id)
    q2, opt2 = _make_question_with_correct_option(pg_session, test.id, module_id=module2.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    # q2 belongs to module2, not the active module1 — must be rejected.
    with pytest.raises(InvalidQuestionReferenceException):
        service.save_answer(attempt.id, student_id, q2.id, selected_option=opt2.id)


# --- E/F/G: module submission, adaptive routing, exam completion ---

def test_module_submit_routes_to_next_module(pg_session):
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Modular Test", duration=60, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    module2 = ExamModule(section_id=section.id, name="Module 2", order_number=1)
    pg_session.add_all([module1, module2])
    pg_session.flush()
    q1, opt1 = _make_question_with_correct_option(pg_session, test.id, module_id=module1.id)
    q2, opt2 = _make_question_with_correct_option(pg_session, test.id, module_id=module2.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()
    service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()

    outcome = service.submit_module(attempt.id, module1.id, student_id)
    pg_session.commit()

    assert outcome["completed"] is False
    assert outcome["next_module_id"] == module2.id
    assert outcome["result"] is None

    m1_progress = pg_session.query(AttemptModuleProgress).filter(
        AttemptModuleProgress.attempt_id == attempt.id, AttemptModuleProgress.module_id == module1.id
    ).one()
    assert m1_progress.status == "submitted"
    assert m1_progress.submitted_at is not None

    m2_progress = pg_session.query(AttemptModuleProgress).filter(
        AttemptModuleProgress.attempt_id == attempt.id, AttemptModuleProgress.module_id == module2.id
    ).one()
    assert m2_progress.status == "in_progress"
    assert m2_progress.question_order == [q2.id]


def test_last_module_submit_completes_exam_and_creates_result(pg_session):
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Single Module Test", duration=60, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    pg_session.add(module1)
    pg_session.flush()
    q1, opt1 = _make_question_with_correct_option(pg_session, test.id, module_id=module1.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()
    service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()

    outcome = service.submit_module(attempt.id, module1.id, student_id)
    pg_session.commit()

    assert outcome["completed"] is True
    assert outcome["next_module_id"] is None
    assert outcome["result"] is not None
    assert outcome["result"].status == "submitted"
    assert outcome["result"].correct_count == 1

    reloaded_attempt = pg_session.query(TestAttempt).filter(TestAttempt.id == attempt.id).one()
    assert reloaded_attempt.status == "submitted"


# --- D (continued): duplicate submit rejected ---

def test_duplicate_module_submit_rejected(pg_session):
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Modular Test", duration=60, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    pg_session.add(module1)
    pg_session.flush()
    q1, opt1 = _make_question_with_correct_option(pg_session, test.id, module_id=module1.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()
    service.submit_module(attempt.id, module1.id, student_id)
    pg_session.commit()

    with pytest.raises(AttemptNotActiveException):
        service.submit_module(attempt.id, module1.id, student_id)


# --- H: timing — expired module lazy auto-finish (Sprint 79) ---
#
# Sprint 79 audit CRITICAL finding: before this sprint, a module whose
# own expires_at had passed (while the whole-attempt Test.duration
# hadn't) left the student permanently stuck — submit_module() raised
# ModuleNotActiveException forever, with no code path that ever
# finalized/advanced the expired module. These tests replace the old
# "stays stuck" assertion with the new, correct lazy-auto-finish
# behavior: an expired module is auto-submitted (scored + routed)
# exactly like an explicit, on-time submit would have been, the first
# time any module-scoped entry point (get_attempt/get_attempt_detail,
# save_answer, submit_attempt, submit_module) touches this attempt.


def test_expired_last_module_auto_finishes_exam_via_get_attempt_detail(pg_session):
    """The exact scenario the old (now-removed) test reproduced the bug
    with: Test.duration=600 vastly outlasts module.duration=10. Before
    Sprint 79, nothing short of waiting 600 minutes ever unstuck this
    attempt. Now, simply calling get_attempt_detail() (an ordinary GET,
    e.g. a page refresh) notices the expired module and auto-finishes
    the whole exam, since this was the only module."""
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Modular Test", duration=600, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0, duration=10)
    pg_session.add(module1)
    pg_session.flush()
    q1, opt1 = _make_question_with_correct_option(pg_session, test.id, module_id=module1.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    # Force the module's own expiry into the past — the whole-attempt
    # Test.duration=600 has NOT expired, so only the module-level lazy
    # check can recover this attempt.
    progress = pg_session.query(AttemptModuleProgress).filter(AttemptModuleProgress.attempt_id == attempt.id).one()
    progress.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    pg_session.commit()

    assert detail.status == "auto_finished"
    assert detail.module_id is None  # no more active module — exam is over

    reloaded_progress = pg_session.query(AttemptModuleProgress).filter(AttemptModuleProgress.attempt_id == attempt.id).one()
    assert reloaded_progress.status == "submitted"
    assert reloaded_progress.submitted_at is not None

    reloaded_attempt = pg_session.query(TestAttempt).filter(TestAttempt.id == attempt.id).one()
    assert reloaded_attempt.status == "auto_finished"

    # A result is now available, exactly as whole-test auto-finish
    # already allows (get_result() never required an explicit submit).
    result = service.get_result(attempt.id, student_id)
    assert result.status == "auto_finished"
    assert result.correct_count == 0  # never answered before expiry


def test_expired_module_with_next_module_auto_routes_forward(pg_session):
    """Two-module exam: module1 expires; module2 has no duration limit.
    Calling get_attempt_detail() must auto-submit module1 (scoring it
    exactly as an on-time submit would) and advance the student straight
    to module2 — the attempt itself stays fully active, no whole-exam
    finalization, since the exam isn't actually complete."""
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Modular Test", duration=600, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0, duration=10)
    module2 = ExamModule(section_id=section.id, name="Module 2", order_number=1)
    pg_session.add_all([module1, module2])
    pg_session.flush()
    q1, opt1 = _make_question_with_correct_option(pg_session, test.id, module_id=module1.id)
    q2, opt2 = _make_question_with_correct_option(pg_session, test.id, module_id=module2.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()
    service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()

    m1_progress = pg_session.query(AttemptModuleProgress).filter(
        AttemptModuleProgress.attempt_id == attempt.id, AttemptModuleProgress.module_id == module1.id
    ).one()
    m1_progress.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    pg_session.commit()

    assert detail.status == "in_progress"  # whole attempt still active
    assert detail.module_id == module2.id  # auto-advanced
    assert detail.questions[0].id == q2.id  # now delivering module2's questions

    reloaded_m1 = pg_session.query(AttemptModuleProgress).filter(
        AttemptModuleProgress.attempt_id == attempt.id, AttemptModuleProgress.module_id == module1.id
    ).one()
    assert reloaded_m1.status == "submitted"
    assert reloaded_m1.submitted_at is not None

    m2_progress = pg_session.query(AttemptModuleProgress).filter(
        AttemptModuleProgress.attempt_id == attempt.id, AttemptModuleProgress.module_id == module2.id
    ).one()
    assert m2_progress.status == "in_progress"


def test_explicit_submit_of_already_lazily_finished_module_raises_not_active(pg_session):
    """A client with stale UI state (it hasn't re-fetched since the
    module auto-finished) that still tries to POST submit for the now-
    stale module_id gets a clean, immediate error — not a silent
    double-process and not the old permanent-409 deadlock. This
    exercises the lazy auto-finish firing INSIDE submit_module() itself
    (no prior get_attempt_detail() call). Since this is the attempt's
    only module, the lazy check also completes/finalizes the whole
    attempt as a side effect — so the outer AttemptService.submit_module()
    rejects the stale call with AttemptNotActiveException (the
    attempt-level "already finished" check, which now correctly runs
    first) rather than a module-level error."""
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Modular Test", duration=600, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0, duration=10)
    pg_session.add(module1)
    pg_session.flush()
    q1, opt1 = _make_question_with_correct_option(pg_session, test.id, module_id=module1.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    progress = pg_session.query(AttemptModuleProgress).filter(AttemptModuleProgress.attempt_id == attempt.id).one()
    progress.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    pg_session.commit()

    with pytest.raises(AttemptNotActiveException):
        service.submit_module(attempt.id, module1.id, student_id)
    pg_session.commit()

    # The module was still auto-finished as a side effect of this very
    # call (the lazy check runs before the explicit-submit body) —
    # confirmed not stuck, unlike the pre-Sprint-79 behavior.
    reloaded = pg_session.query(AttemptModuleProgress).filter(AttemptModuleProgress.attempt_id == attempt.id).one()
    assert reloaded.status == "submitted"


def test_explicit_submit_of_stale_module_after_auto_route_raises_module_not_active(pg_session):
    """Two-module variant of the above: module1 expires and auto-routes
    to module2 (the attempt itself stays ACTIVE_STATUSES), so a stale
    client still trying to POST submit for module1 now correctly fails
    the MODULE-level check (ModuleNotActiveException — "already
    submitted"), not the attempt-level one, since the attempt is very
    much still active."""
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Modular Test", duration=600, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0, duration=10)
    module2 = ExamModule(section_id=section.id, name="Module 2", order_number=1)
    pg_session.add_all([module1, module2])
    pg_session.flush()
    q1, opt1 = _make_question_with_correct_option(pg_session, test.id, module_id=module1.id)
    q2, opt2 = _make_question_with_correct_option(pg_session, test.id, module_id=module2.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    m1_progress = pg_session.query(AttemptModuleProgress).filter(
        AttemptModuleProgress.attempt_id == attempt.id, AttemptModuleProgress.module_id == module1.id
    ).one()
    m1_progress.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    pg_session.commit()

    with pytest.raises(ModuleNotActiveException):
        service.submit_module(attempt.id, module1.id, student_id)
    pg_session.commit()

    reloaded_attempt = pg_session.query(TestAttempt).filter(TestAttempt.id == attempt.id).one()
    assert reloaded_attempt.status == "in_progress"  # whole attempt unaffected, still active

    m2_progress = pg_session.query(AttemptModuleProgress).filter(
        AttemptModuleProgress.attempt_id == attempt.id, AttemptModuleProgress.module_id == module2.id
    ).one()
    assert m2_progress.status == "in_progress"  # auto-routed forward as a side effect


def test_non_expired_active_module_is_untouched_by_lazy_check(pg_session):
    """Safety/regression: the lazy auto-finish check must be a true
    no-op for the overwhelming common case — an active module that
    simply hasn't expired yet. Every pre-Sprint-79 test in this file
    exercises this implicitly; this test pins it explicitly."""
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Modular Test", duration=600, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0, duration=60)
    pg_session.add(module1)
    pg_session.flush()
    q1, opt1 = _make_question_with_correct_option(pg_session, test.id, module_id=module1.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    pg_session.commit()

    assert detail.status == "in_progress"
    assert detail.module_id == module1.id

    progress = pg_session.query(AttemptModuleProgress).filter(AttemptModuleProgress.attempt_id == attempt.id).one()
    assert progress.status == "in_progress"
    assert progress.submitted_at is None


# --- I: IDOR — another student's module ---

def test_cannot_submit_another_students_module(pg_session):
    student_a = _make_student(pg_session)
    student_b = _make_student(pg_session)
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Modular Test", duration=60, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    pg_session.add(module1)
    pg_session.flush()
    _make_question_with_correct_option(pg_session, test.id, module_id=module1.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt_a = service.start_attempt(test.id, student_a)
    pg_session.commit()

    # Student B has never started this test — no attempt of theirs
    # exists, so attempt ownership itself already fails first.
    with pytest.raises(Exception):
        service.submit_module(attempt_a.id, module1.id, student_b)


def test_cannot_access_unrelated_module_id(pg_session):
    """A module_id that exists (belongs to a DIFFERENT test/attempt
    entirely) must be rejected the same as a nonexistent one."""
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Modular Test", duration=60, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    pg_session.add(module1)
    pg_session.flush()
    _make_question_with_correct_option(pg_session, test.id, module_id=module1.id)

    # An unrelated module the attempt was never assigned.
    other_section = ExamSection(test_id=test.id, name="Other", order_number=1)
    pg_session.add(other_section)
    pg_session.flush()
    unrelated_module = ExamModule(section_id=other_section.id, name="Unrelated", order_number=0)
    pg_session.add(unrelated_module)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    with pytest.raises(ModuleNotFoundForAttemptException):
        service.submit_module(attempt.id, unrelated_module.id, student_id)


# --- CRITICAL-1 regression: true concurrent submit_module() ---

def test_concurrent_module_submit_is_race_safe():
    """Sprint 50 CRITICAL-1 fix regression test.

    Deliberately does NOT use the pg_session fixture — pg_session
    (Sprint 40's infrastructure) runs the entire test inside one
    SAVEPOINT-based outer transaction that is rolled back at the end;
    pg_session.commit() only releases a savepoint, it never becomes
    visible to a genuinely separate database connection. True
    concurrency testing needs actually-separate, really-committing
    PostgreSQL transactions, so this test manages its own sessions
    end-to-end (and cleans up what it created afterward, since nothing
    here benefits from pg_session's automatic rollback).

    Before the fix: both threads could pass validate_active() before
    either committed, and — depending on exact timing — the SECOND
    thread's routing decision could see the first thread's
    already-created next module as "already progressed" and incorrectly
    conclude the exam was complete, finalizing the whole attempt while
    the next module was still sitting at status="in_progress".

    After the fix: the second thread's locked re-fetch
    (get_for_attempt_and_module_locked) blocks until the first thread's
    transaction commits, then sees the post-commit "submitted" status
    and is correctly rejected as a duplicate submission — it never
    reaches the routing/finalization logic at all.
    """
    from sqlalchemy.orm import sessionmaker
    from app.db.database import engine
    from app.modules.attempts.models import AttemptModuleProgress
    from app.modules.attempts.module_execution_service import ModuleExecutionService
    from app.modules.attempts.repository import AnswerRepository, AttemptModuleProgressRepository, AttemptRepository
    from app.modules.questions.repository import OptionRepository, QuestionRepository
    from app.modules.roles.models import Role
    from app.modules.topics.models import Topic
    from app.modules.grades.models import Grade
    from app.modules.tests.repository import ExamModuleRepository, TestRepository

    Session = sessionmaker(bind=engine)

    def make_service(s):
        return AttemptService(
            AttemptRepository(s), AnswerRepository(s), TestRepository(s), QuestionRepository(s), OptionRepository(s),
            ModuleExecutionService(ExamModuleRepository(s), AttemptModuleProgressRepository(s), QuestionRepository(s), AnswerRepository(s), AttemptRepository(s)),
            ExamModuleRepository(s),
        )

    setup = Session()
    try:
        role = setup.query(Role).filter(Role.name == "Student").one()
        user = User(role_id=role.id, first_name="CC", last_name="RT", email=f"ccrt-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
        setup.add(user)
        setup.flush()
        student_id = user.id
        subject = Subject(name=f"S-{uuid.uuid4()}")
        setup.add(subject)
        setup.flush()
        test = Test(subject_id=subject.id, title="Concurrency Test", duration=60, question_count=0, status="published")
        setup.add(test)
        setup.flush()
        section = ExamSection(test_id=test.id, name="Section", order_number=0)
        setup.add(section)
        setup.flush()
        module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0)
        module2 = ExamModule(section_id=section.id, name="Module 2", order_number=1)
        setup.add_all([module1, module2])
        setup.flush()
        q1 = Question(test_id=test.id, question_text="Q1", question_type="single_choice", score=1, module_id=module1.id)
        setup.add(q1)
        setup.flush()
        opt1 = QuestionOption(question_id=q1.id, option_text="A", is_correct=True)
        setup.add(opt1)
        q2 = Question(test_id=test.id, question_text="Q2", question_type="single_choice", score=1, module_id=module2.id)
        setup.add(q2)
        setup.flush()
        opt2 = QuestionOption(question_id=q2.id, option_text="A", is_correct=True)
        setup.add(opt2)
        setup.commit()

        service = make_service(setup)
        attempt = service.start_attempt(test.id, student_id)
        attempt_id, module1_id, module2_id = attempt.id, module1.id, module2.id
        test_id, section_id, subject_id, q1_id, q2_id = test.id, section.id, subject.id, q1.id, q2.id
        setup.commit()
    finally:
        setup.close()

    outcomes = {}

    def worker(name: str):
        s = Session()
        svc = make_service(s)
        try:
            r = svc.submit_module(attempt_id, module1_id, student_id)
            s.commit()
            outcomes[name] = ("OK", r)
        except Exception as e:
            s.rollback()
            outcomes[name] = ("ERROR", type(e).__name__)
        finally:
            s.close()

    t1 = threading.Thread(target=worker, args=("A",))
    t2 = threading.Thread(target=worker, args=("B",))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    results = [outcomes.get("A"), outcomes.get("B")]
    successes = [r for r in results if r is not None and r[0] == "OK"]
    failures = [r for r in results if r is not None and r[0] == "ERROR"]

    try:
        # Exactly one request succeeds; the other is rejected as a duplicate.
        assert len(successes) == 1, f"expected exactly 1 success, got {results}"
        assert len(failures) == 1, f"expected exactly 1 rejection, got {results}"
        assert failures[0][1] == "ModuleNotActiveException"

        verify = Session()
        try:
            m1_progress = verify.query(AttemptModuleProgress).filter(
                AttemptModuleProgress.attempt_id == attempt_id, AttemptModuleProgress.module_id == module1_id
            ).one()
            assert m1_progress.status == "submitted"

            m2_progress = verify.query(AttemptModuleProgress).filter(
                AttemptModuleProgress.attempt_id == attempt_id, AttemptModuleProgress.module_id == module2_id
            ).one()
            assert m2_progress.status == "in_progress"  # NOT skipped/finalized-away

            reloaded_attempt = verify.query(TestAttempt).filter(TestAttempt.id == attempt_id).one()
            assert reloaded_attempt.status == "in_progress"  # the exam is NOT prematurely finalized
        finally:
            verify.close()
    finally:
        # This test committed real data outside pg_session's automatic
        # rollback — clean it up explicitly so it doesn't linger.
        cleanup = Session()
        try:
            cleanup.query(AttemptModuleProgress).filter(AttemptModuleProgress.attempt_id == attempt_id).delete()
            cleanup.query(TestAttempt).filter(TestAttempt.id == attempt_id).delete()
            cleanup.query(QuestionOption).filter(QuestionOption.question_id.in_([q1_id, q2_id])).delete(synchronize_session=False)
            cleanup.query(Question).filter(Question.test_id == test_id).delete()
            cleanup.query(ExamModule).filter(ExamModule.section_id == section_id).delete()
            cleanup.query(ExamSection).filter(ExamSection.id == section_id).delete()
            cleanup.query(Test).filter(Test.id == test_id).delete()
            cleanup.query(Subject).filter(Subject.id == subject_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()


def test_concurrent_lazy_auto_finish_is_race_safe():
    """Sprint 79 — concurrency regression for the new lazy per-module
    expiry path. Two concurrent get_attempt_detail() calls (e.g. two
    browser tabs, or a page double-refresh) against the SAME expired
    module must not both route past it: exactly like
    test_concurrent_module_submit_is_race_safe() above,
    get_for_attempt_and_module_locked() inside
    auto_finish_active_module_if_expired() serializes the two callers —
    the second one's locked re-fetch observes the first's already-
    "submitted" row and (status != IN_PROGRESS) returns None (a no-op),
    never double-scoring/double-routing. Uses real, separately-
    committing sessions for the same reason the sibling test does —
    pg_session's SAVEPOINT rollback never becomes visible to a second
    connection, so true concurrency needs real sessions."""
    from sqlalchemy.orm import sessionmaker
    from app.db.database import engine
    from app.modules.attempts.models import AttemptModuleProgress
    from app.modules.attempts.module_execution_service import ModuleExecutionService
    from app.modules.attempts.repository import AnswerRepository, AttemptModuleProgressRepository, AttemptRepository
    from app.modules.questions.repository import OptionRepository, QuestionRepository
    from app.modules.roles.models import Role
    from app.modules.tests.repository import ExamModuleRepository, TestRepository

    Session = sessionmaker(bind=engine)

    def make_service(s):
        return AttemptService(
            AttemptRepository(s), AnswerRepository(s), TestRepository(s), QuestionRepository(s), OptionRepository(s),
            ModuleExecutionService(ExamModuleRepository(s), AttemptModuleProgressRepository(s), QuestionRepository(s), AnswerRepository(s), AttemptRepository(s)),
            ExamModuleRepository(s),
        )

    setup = Session()
    try:
        role = setup.query(Role).filter(Role.name == "Student").one()
        user = User(role_id=role.id, first_name="LZ", last_name="FN", email=f"lzfn-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
        setup.add(user)
        setup.flush()
        student_id = user.id
        subject = Subject(name=f"S-{uuid.uuid4()}")
        setup.add(subject)
        setup.flush()
        test = Test(subject_id=subject.id, title="Lazy Concurrency Test", duration=600, question_count=0, status="published")
        setup.add(test)
        setup.flush()
        section = ExamSection(test_id=test.id, name="Section", order_number=0)
        setup.add(section)
        setup.flush()
        module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0, duration=10)
        module2 = ExamModule(section_id=section.id, name="Module 2", order_number=1)
        setup.add_all([module1, module2])
        setup.flush()
        q1 = Question(test_id=test.id, question_text="Q1", question_type="single_choice", score=1, module_id=module1.id)
        setup.add(q1)
        setup.flush()
        opt1 = QuestionOption(question_id=q1.id, option_text="A", is_correct=True)
        setup.add(opt1)
        q2 = Question(test_id=test.id, question_text="Q2", question_type="single_choice", score=1, module_id=module2.id)
        setup.add(q2)
        setup.flush()
        opt2 = QuestionOption(question_id=q2.id, option_text="A", is_correct=True)
        setup.add(opt2)
        setup.commit()

        service = make_service(setup)
        attempt = service.start_attempt(test.id, student_id)
        attempt_id, module1_id, module2_id = attempt.id, module1.id, module2.id
        test_id, section_id, subject_id, q1_id, q2_id = test.id, section.id, subject.id, q1.id, q2.id
        setup.commit()

        m1_progress = setup.query(AttemptModuleProgress).filter(
            AttemptModuleProgress.attempt_id == attempt_id, AttemptModuleProgress.module_id == module1_id
        ).one()
        m1_progress.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        setup.commit()
    finally:
        setup.close()

    outcomes = {}

    def worker(name: str):
        s = Session()
        svc = make_service(s)
        try:
            detail = svc.get_attempt_detail(attempt_id, student_id)
            s.commit()
            outcomes[name] = ("OK", detail.module_id)
        except Exception as e:
            s.rollback()
            outcomes[name] = ("ERROR", type(e).__name__)
        finally:
            s.close()

    t1 = threading.Thread(target=worker, args=("A",))
    t2 = threading.Thread(target=worker, args=("B",))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    try:
        # Both GETs succeed (reading state is never rejected) and BOTH
        # observe the same, single post-auto-finish outcome — module2
        # active, exactly once routed to, never double-routed.
        assert outcomes["A"] == ("OK", module2_id)
        assert outcomes["B"] == ("OK", module2_id)

        verify = Session()
        try:
            m1_progress = verify.query(AttemptModuleProgress).filter(
                AttemptModuleProgress.attempt_id == attempt_id, AttemptModuleProgress.module_id == module1_id
            ).one()
            assert m1_progress.status == "submitted"

            # Exactly ONE module2 progress row — not two (which would
            # mean both threads raced past the lock and each created
            # their own next-module progress row).
            m2_rows = verify.query(AttemptModuleProgress).filter(
                AttemptModuleProgress.attempt_id == attempt_id, AttemptModuleProgress.module_id == module2_id
            ).all()
            assert len(m2_rows) == 1
            assert m2_rows[0].status == "in_progress"

            reloaded_attempt = verify.query(TestAttempt).filter(TestAttempt.id == attempt_id).one()
            assert reloaded_attempt.status == "in_progress"
        finally:
            verify.close()
    finally:
        cleanup = Session()
        try:
            cleanup.query(AttemptModuleProgress).filter(AttemptModuleProgress.attempt_id == attempt_id).delete()
            cleanup.query(TestAttempt).filter(TestAttempt.id == attempt_id).delete()
            cleanup.query(QuestionOption).filter(QuestionOption.question_id.in_([q1_id, q2_id])).delete(synchronize_session=False)
            cleanup.query(Question).filter(Question.test_id == test_id).delete()
            cleanup.query(ExamModule).filter(ExamModule.section_id == section_id).delete()
            cleanup.query(ExamSection).filter(ExamSection.id == section_id).delete()
            cleanup.query(Test).filter(Test.id == test_id).delete()
            cleanup.query(Subject).filter(Subject.id == subject_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()
