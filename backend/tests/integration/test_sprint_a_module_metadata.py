"""
Sprint A (post-75) — student-scoped module/section metadata, against
real PostgreSQL (Sprint 40's infrastructure — pg_session,
TEST_DATABASE_URL).

Scope: AttemptService.get_module_for_attempt() (new) and
AttemptDetailOut.module_id (new, additive field on get_attempt_detail()).
Both are read-only additions on top of the Sprint 50 module-execution
engine — no scoring/routing/timing logic is touched.

Constructs AttemptService directly with real repositories, matching
this project's existing integration-test style for this engine (see
test_module_execution.py) rather than going through FastAPI's DI.
"""
import uuid

import pytest

from app.modules.attempts.exceptions import AttemptNotFoundException, ModuleNotFoundForAttemptException
from app.modules.attempts.module_execution_service import ModuleExecutionService
from app.modules.attempts.repository import AnswerRepository, AttemptModuleProgressRepository, AttemptRepository
from app.modules.attempts.service import AttemptService
from app.modules.questions.models import Question, QuestionOption
from app.modules.questions.repository import OptionRepository, QuestionRepository
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import ExamModule, ExamSection, Test
from app.modules.tests.repository import ExamModuleRepository, ExamSectionRepository, TestRepository
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
        ExamSectionRepository(pg_session),
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


def _make_modular_test(pg_session, module1_duration=None):
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Modular Test", duration=60, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Reading and Writing", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0, duration=module1_duration)
    module2 = ExamModule(section_id=section.id, name="Module 2", order_number=1)
    pg_session.add_all([module1, module2])
    pg_session.flush()
    _make_question_with_correct_option(pg_session, test.id, module_id=module1.id)
    _make_question_with_correct_option(pg_session, test.id, module_id=module2.id)
    pg_session.commit()
    return test, section, module1, module2


# --- get_module_for_attempt() ---

def test_get_module_for_attempt_returns_name_and_section_for_active_module(pg_session):
    student_id = _make_student(pg_session)
    test, section, module1, module2 = _make_modular_test(pg_session, module1_duration=10)

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    out = service.get_module_for_attempt(attempt.id, module1.id, student_id)
    assert out.id == module1.id
    assert out.name == "Module 1"
    assert out.order_number == 0
    assert out.duration == 10
    assert out.section_id == section.id
    assert out.section_name == "Reading and Writing"
    assert out.section_order_number == 0


def test_get_module_for_attempt_works_for_routed_next_module(pg_session):
    """submit_module() already creates the next module's progress row
    before returning next_module_id — this endpoint must be able to
    describe that module immediately, without a further navigation
    call."""
    student_id = _make_student(pg_session)
    test, section, module1, module2 = _make_modular_test(pg_session)

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    outcome = service.submit_module(attempt.id, module1.id, student_id)
    pg_session.commit()
    assert outcome["completed"] is False
    assert outcome["next_module_id"] == module2.id

    out = service.get_module_for_attempt(attempt.id, module2.id, student_id)
    assert out.id == module2.id
    assert out.name == "Module 2"
    assert out.order_number == 1


def test_get_module_for_attempt_rejects_unrelated_module(pg_session):
    """A module_id that exists but was never assigned to this attempt
    (same IDOR shape as submit_module's own guard) must 404, not leak
    its name/section."""
    student_id = _make_student(pg_session)
    test, section, module1, module2 = _make_modular_test(pg_session)

    other_section = ExamSection(test_id=test.id, name="Math", order_number=1)
    pg_session.add(other_section)
    pg_session.flush()
    unrelated_module = ExamModule(section_id=other_section.id, name="Unrelated", order_number=0)
    pg_session.add(unrelated_module)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    with pytest.raises(ModuleNotFoundForAttemptException):
        service.get_module_for_attempt(attempt.id, unrelated_module.id, student_id)


def test_get_module_for_attempt_rejects_other_students_attempt(pg_session):
    student_a = _make_student(pg_session)
    student_b = _make_student(pg_session)
    test, section, module1, module2 = _make_modular_test(pg_session)

    service = _make_service(pg_session)
    attempt_a = service.start_attempt(test.id, student_a)
    pg_session.commit()

    # _get_owned_attempt() rejects this before module lookup is ever
    # reached — same AttemptNotFoundException every other attempt-scoped
    # endpoint raises for "exists but isn't yours".
    with pytest.raises(AttemptNotFoundException):
        service.get_module_for_attempt(attempt_a.id, module1.id, student_b)


def test_get_module_for_attempt_rejects_nonexistent_attempt(pg_session):
    student_id = _make_student(pg_session)
    test, section, module1, module2 = _make_modular_test(pg_session)

    service = _make_service(pg_session)

    # Same AttemptNotFoundException as above — a nonexistent attempt_id
    # is rejected by _get_owned_attempt() before any module lookup.
    with pytest.raises(AttemptNotFoundException):
        service.get_module_for_attempt(uuid.uuid4(), module1.id, student_id)


def test_get_module_for_attempt_raises_for_non_modular_test(pg_session):
    """A non-modular attempt has no AttemptModuleProgress rows at all —
    any module_id must be rejected the same way an unrelated one is."""
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Plain Test", duration=30, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    _make_question_with_correct_option(pg_session, test.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    with pytest.raises(ModuleNotFoundForAttemptException):
        service.get_module_for_attempt(attempt.id, uuid.uuid4(), student_id)


def test_get_module_for_attempt_raises_without_section_repo_configured(pg_session):
    """Legacy/partial AttemptService construction (section_repository
    left at its default None) must report not-found rather than
    crashing — mirrors module_execution_service's own None-guard
    convention elsewhere in this service."""
    student_id = _make_student(pg_session)
    test, section, module1, module2 = _make_modular_test(pg_session)

    legacy_service = AttemptService(
        AttemptRepository(pg_session), AnswerRepository(pg_session), TestRepository(pg_session),
        QuestionRepository(pg_session), OptionRepository(pg_session),
        ModuleExecutionService(
            ExamModuleRepository(pg_session), AttemptModuleProgressRepository(pg_session),
            QuestionRepository(pg_session), AnswerRepository(pg_session), AttemptRepository(pg_session),
        ),
        ExamModuleRepository(pg_session),
        # section_repository intentionally omitted -> defaults to None
    )
    attempt = legacy_service.start_attempt(test.id, student_id)
    pg_session.commit()

    with pytest.raises(ModuleNotFoundForAttemptException):
        legacy_service.get_module_for_attempt(attempt.id, module1.id, student_id)


# --- AttemptDetailOut.module_id ---

def test_attempt_detail_includes_active_module_id(pg_session):
    student_id = _make_student(pg_session)
    test, section, module1, module2 = _make_modular_test(pg_session)

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    assert detail.module_id == module1.id


def test_attempt_detail_module_id_updates_after_routing(pg_session):
    student_id = _make_student(pg_session)
    test, section, module1, module2 = _make_modular_test(pg_session)

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    service.submit_module(attempt.id, module1.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    assert detail.module_id == module2.id


def test_attempt_detail_module_id_is_none_for_non_modular_test(pg_session):
    """Regression guard — every pre-existing non-modular attempt must
    keep getting module_id=None, never a crash or a stray value."""
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Plain Test", duration=30, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    _make_question_with_correct_option(pg_session, test.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    assert detail.module_id is None


def test_attempt_detail_module_id_is_none_once_exam_fully_submitted(pg_session):
    """After the last module is submitted, there is no active progress
    row left — module_id must fall back to None rather than stale data."""
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
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    outcome = service.submit_module(attempt.id, module1.id, student_id)
    pg_session.commit()
    assert outcome["completed"] is True

    detail = service.get_attempt_detail(attempt.id, student_id)
    assert detail.module_id is None
