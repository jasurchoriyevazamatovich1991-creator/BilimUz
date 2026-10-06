"""
Sprint 76 — module-scoped timer contract, against real PostgreSQL
(Sprint 40's infrastructure — pg_session, TEST_DATABASE_URL).

Scope: AttemptDetailOut.module_expires_at (new, additive field on
get_attempt_detail()) — the one backend contract gap the Sprint 76
audit found: AttemptModuleProgress.expires_at was computed and enforced
server-side since Sprint 50 (ModuleExecutionService._create_module_progress/
validate_active), but never serialized anywhere a student could read
it, so a frontend module timer had no authoritative deadline to render.
Read-only addition — no scoring/routing/timing enforcement logic is
touched (validate_active() itself is unchanged).

Matches this project's existing integration-test style for this engine
(see test_module_execution.py, test_sprint_a_module_metadata.py):
AttemptService constructed directly with real repositories, not
through FastAPI's DI.
"""
import uuid
from datetime import datetime, timezone

import pytest

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


def test_attempt_detail_exposes_module_expires_at_when_module_has_duration(pg_session):
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
    pg_session.add(module1)
    pg_session.flush()
    _make_question_with_correct_option(pg_session, test.id, module_id=module1.id)
    pg_session.commit()

    service = _make_service(pg_session)
    before = datetime.now(timezone.utc)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    assert detail.module_expires_at is not None
    # module1.duration=10 minutes -> expires_at is ~10 minutes after start,
    # strictly after "before" and not absurdly far in the future.
    assert detail.module_expires_at > before
    assert (detail.module_expires_at - before).total_seconds() <= 11 * 60


def test_attempt_detail_module_expires_at_is_none_when_module_has_no_duration(pg_session):
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
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0)  # duration=None
    pg_session.add(module1)
    pg_session.flush()
    _make_question_with_correct_option(pg_session, test.id, module_id=module1.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    assert detail.module_id == module1.id
    assert detail.module_expires_at is None


def test_attempt_detail_module_expires_at_updates_after_routing(pg_session):
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
    module2 = ExamModule(section_id=section.id, name="Module 2", order_number=1, duration=20)
    pg_session.add_all([module1, module2])
    pg_session.flush()
    _make_question_with_correct_option(pg_session, test.id, module_id=module1.id)
    _make_question_with_correct_option(pg_session, test.id, module_id=module2.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail_before = service.get_attempt_detail(attempt.id, student_id)
    expires_before = detail_before.module_expires_at

    service.submit_module(attempt.id, module1.id, student_id)
    pg_session.commit()

    detail_after = service.get_attempt_detail(attempt.id, student_id)
    assert detail_after.module_id == module2.id
    assert detail_after.module_expires_at is not None
    assert detail_after.module_expires_at != expires_before


def test_attempt_detail_module_expires_at_is_none_for_non_modular_test(pg_session):
    """Regression guard — the whole-attempt expires_at field is
    untouched; this new field stays None for every non-modular attempt,
    exactly like module_id already does."""
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
    assert detail.module_expires_at is None
    assert detail.expires_at is not None  # whole-attempt timer untouched
