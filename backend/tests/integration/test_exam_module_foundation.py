"""
Sprint 46 — Generic Exam Module Foundation integration tests, against
real PostgreSQL (Sprint 40's infrastructure — pg_session, TEST_DATABASE_URL).

Covers items A-M from the Sprint 46 implementation prompt's test plan.
No SAT adaptive routing, no new endpoints, no frontend — pure data
foundation, verified against real FK/UNIQUE/ON DELETE behavior that
mocks cannot check.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.modules.attempts.models import AttemptModuleProgress, AttemptStatus, TestAttempt
from app.modules.questions.models import Question
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import ExamModule, ExamSection, Test
from app.modules.users.models import User, UserStatus


def _make_student(pg_session) -> uuid.UUID:
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name="M", last_name="S", email=f"m-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    pg_session.flush()
    return user.id


def _make_test_with_section(pg_session) -> Test:
    subject = Subject(name=f"Subject-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="SAT-like Test", duration=60, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    return test


# --- A/B/C: ExamModule creation, belongs to ExamSection, order uniqueness ---

def test_exam_module_belongs_to_exam_section(pg_session):
    test = _make_test_with_section(pg_session)
    section = ExamSection(test_id=test.id, name="Math", order_number=0)
    pg_session.add(section)
    pg_session.flush()

    module = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    pg_session.add(module)
    pg_session.flush()

    reloaded = pg_session.query(ExamModule).filter(ExamModule.id == module.id).one()
    assert reloaded.section_id == section.id
    assert reloaded.name == "Module 1"


def test_exam_module_order_unique_within_same_section(pg_session):
    test = _make_test_with_section(pg_session)
    section = ExamSection(test_id=test.id, name="Math", order_number=0)
    pg_session.add(section)
    pg_session.flush()

    pg_session.add(ExamModule(section_id=section.id, name="Module 1", order_number=0))
    pg_session.flush()

    pg_session.add(ExamModule(section_id=section.id, name="Duplicate", order_number=0))
    try:
        pg_session.flush()
        assert False, "expected IntegrityError from UNIQUE(section_id, order_number)"
    except IntegrityError:
        pg_session.rollback()


def test_two_different_sections_can_each_have_module_order_zero(pg_session):
    test = _make_test_with_section(pg_session)
    section_a = ExamSection(test_id=test.id, name="Reading and Writing", order_number=0)
    section_b = ExamSection(test_id=test.id, name="Math", order_number=1)
    pg_session.add_all([section_a, section_b])
    pg_session.flush()

    pg_session.add(ExamModule(section_id=section_a.id, name="Module 1", order_number=0))
    pg_session.add(ExamModule(section_id=section_b.id, name="Module 1", order_number=0))
    pg_session.flush()  # must not raise


# --- D/E: Question.module_id, SET NULL on module delete ---

def test_question_module_id_references_exam_module(pg_session):
    test = _make_test_with_section(pg_session)
    section = ExamSection(test_id=test.id, name="Math", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    pg_session.add(module)
    pg_session.flush()

    question = Question(test_id=test.id, question_text="2+2=?", question_type="single_choice", score=1, module_id=module.id)
    pg_session.add(question)
    pg_session.flush()

    reloaded = pg_session.query(Question).filter(Question.id == question.id).one()
    assert reloaded.module_id == module.id
    # test_id/section_id remain the question's own, untouched fields.
    assert reloaded.test_id == test.id


def test_deleting_module_sets_question_module_id_to_null(pg_session):
    test = _make_test_with_section(pg_session)
    section = ExamSection(test_id=test.id, name="Math", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    pg_session.add(module)
    pg_session.flush()
    question = Question(test_id=test.id, question_text="Q", question_type="single_choice", score=1, module_id=module.id)
    pg_session.add(question)
    pg_session.flush()

    pg_session.delete(module)
    pg_session.commit()

    reloaded = pg_session.query(Question).filter(Question.id == question.id).one()
    assert reloaded.module_id is None
    # The question itself is NOT deleted — CASCADE would be wrong here.
    assert reloaded.test_id == test.id


# --- F/G: AttemptModuleProgress creation, UNIQUE(attempt_id, module_id) ---

def test_attempt_module_progress_creation(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test_with_section(pg_session)
    section = ExamSection(test_id=test.id, name="Math", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    pg_session.add(module)
    pg_session.flush()
    attempt = TestAttempt(user_id=student_id, test_id=test.id, status=AttemptStatus.IN_PROGRESS, start_time=datetime.now(timezone.utc))
    pg_session.add(attempt)
    pg_session.flush()

    progress = AttemptModuleProgress(attempt_id=attempt.id, module_id=module.id, status=AttemptStatus.IN_PROGRESS)
    pg_session.add(progress)
    pg_session.flush()

    reloaded = pg_session.query(AttemptModuleProgress).filter(AttemptModuleProgress.id == progress.id).one()
    assert reloaded.attempt_id == attempt.id
    assert reloaded.module_id == module.id
    assert reloaded.status == "in_progress"


def test_unique_attempt_id_module_id_enforced(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test_with_section(pg_session)
    section = ExamSection(test_id=test.id, name="Math", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    pg_session.add(module)
    pg_session.flush()
    attempt = TestAttempt(user_id=student_id, test_id=test.id, status=AttemptStatus.IN_PROGRESS, start_time=datetime.now(timezone.utc))
    pg_session.add(attempt)
    pg_session.flush()

    pg_session.add(AttemptModuleProgress(attempt_id=attempt.id, module_id=module.id, status=AttemptStatus.IN_PROGRESS))
    pg_session.flush()

    pg_session.add(AttemptModuleProgress(attempt_id=attempt.id, module_id=module.id, status=AttemptStatus.IN_PROGRESS))
    try:
        pg_session.flush()
        assert False, "expected IntegrityError from UNIQUE(attempt_id, module_id)"
    except IntegrityError:
        pg_session.rollback()


# --- H/I: question_order snapshot persistence, unaffected by later changes ---

def test_question_order_snapshot_persists_and_survives_later_module_question_changes(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test_with_section(pg_session)
    section = ExamSection(test_id=test.id, name="Math", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    pg_session.add(module)
    pg_session.flush()

    q1 = Question(test_id=test.id, question_text="Q1", question_type="single_choice", score=1, module_id=module.id)
    q2 = Question(test_id=test.id, question_text="Q2", question_type="single_choice", score=1, module_id=module.id)
    pg_session.add_all([q1, q2])
    pg_session.flush()

    attempt = TestAttempt(user_id=student_id, test_id=test.id, status=AttemptStatus.IN_PROGRESS, start_time=datetime.now(timezone.utc))
    pg_session.add(attempt)
    pg_session.flush()

    snapshot = [q1.id, q2.id]
    progress = AttemptModuleProgress(attempt_id=attempt.id, module_id=module.id, status=AttemptStatus.IN_PROGRESS, question_order=snapshot)
    pg_session.add(progress)
    pg_session.commit()

    # A "later change" to the module's live question set — a THIRD
    # question added to the module after the snapshot was taken.
    q3 = Question(test_id=test.id, question_text="Q3 added later", question_type="single_choice", score=1, module_id=module.id)
    pg_session.add(q3)
    pg_session.commit()

    reloaded = pg_session.query(AttemptModuleProgress).filter(AttemptModuleProgress.id == progress.id).one()
    assert reloaded.question_order == snapshot
    assert q3.id not in reloaded.question_order


# --- J/K: existing sectionless/moduleless questions and attempts unaffected ---

def test_existing_moduleless_question_unaffected(pg_session):
    test = _make_test_with_section(pg_session)
    question = Question(test_id=test.id, question_text="No module", question_type="single_choice", score=1)
    pg_session.add(question)
    pg_session.flush()

    reloaded = pg_session.query(Question).filter(Question.id == question.id).one()
    assert reloaded.module_id is None
    assert reloaded.section_id is None


def test_existing_attempt_without_module_progress_behaves_as_before(pg_session):
    """An attempt against a moduleless test simply has zero
    AttemptModuleProgress rows — no behavior change."""
    student_id = _make_student(pg_session)
    test = _make_test_with_section(pg_session)
    attempt = TestAttempt(user_id=student_id, test_id=test.id, status=AttemptStatus.IN_PROGRESS, start_time=datetime.now(timezone.utc))
    pg_session.add(attempt)
    pg_session.commit()

    progress_rows = pg_session.query(AttemptModuleProgress).filter(AttemptModuleProgress.attempt_id == attempt.id).all()
    assert progress_rows == []
