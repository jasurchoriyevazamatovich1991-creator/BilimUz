"""
Sprint 47 — IELTS Engine Foundation integration tests, against real
PostgreSQL (Sprint 40's infrastructure — pg_session, TEST_DATABASE_URL).

No IELTS scoring, no band conversion, no matching engine, no
endpoints, no frontend — pure data foundation, verified against real
FK/UNIQUE/ON DELETE behavior that mocks cannot check.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.modules.attempts.models import AttemptStatus, TestAttempt
from app.modules.questions.models import Question
from app.modules.results.models import Result, ResultSection
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import ExamSection, QuestionGroup, Test
from app.modules.users.models import User, UserStatus


def _make_student(pg_session) -> uuid.UUID:
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name="I", last_name="S", email=f"i-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    pg_session.flush()
    return user.id


def _make_test(pg_session) -> Test:
    subject = Subject(name=f"Subject-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="IELTS-like Test", duration=60, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    return test


# --- QuestionGroup creation, belongs to Test, order uniqueness ---

def test_question_group_belongs_to_test(pg_session):
    test = _make_test(pg_session)
    group = QuestionGroup(test_id=test.id, title="Passage 1", stimulus_text="Some passage text.", order_number=0)
    pg_session.add(group)
    pg_session.flush()

    reloaded = pg_session.query(QuestionGroup).filter(QuestionGroup.id == group.id).one()
    assert reloaded.test_id == test.id
    assert reloaded.title == "Passage 1"
    assert reloaded.stimulus_text == "Some passage text."


def test_question_group_stimulus_text_nullable(pg_session):
    test = _make_test(pg_session)
    group = QuestionGroup(test_id=test.id, title="No stimulus yet", order_number=0)
    pg_session.add(group)
    pg_session.flush()

    reloaded = pg_session.query(QuestionGroup).filter(QuestionGroup.id == group.id).one()
    assert reloaded.stimulus_text is None


def test_question_group_order_unique_within_same_test(pg_session):
    test = _make_test(pg_session)
    pg_session.add(QuestionGroup(test_id=test.id, title="Passage 1", order_number=0))
    pg_session.flush()

    pg_session.add(QuestionGroup(test_id=test.id, title="Duplicate order", order_number=0))
    try:
        pg_session.flush()
        assert False, "expected IntegrityError from UNIQUE(test_id, order_number)"
    except IntegrityError:
        pg_session.rollback()


def test_two_different_tests_can_each_have_group_order_zero(pg_session):
    test_a = _make_test(pg_session)
    test_b = _make_test(pg_session)
    pg_session.add(QuestionGroup(test_id=test_a.id, title="A Passage", order_number=0))
    pg_session.add(QuestionGroup(test_id=test_b.id, title="B Passage", order_number=0))
    pg_session.flush()  # must not raise


# --- Question.group_id: nullable, relation, SET NULL on delete ---

def test_question_group_id_nullable(pg_session):
    test = _make_test(pg_session)
    question = Question(test_id=test.id, question_text="No group", question_type="single_choice", score=1)
    pg_session.add(question)
    pg_session.flush()

    reloaded = pg_session.query(Question).filter(Question.id == question.id).one()
    assert reloaded.group_id is None


def test_question_to_question_group_relation(pg_session):
    test = _make_test(pg_session)
    group = QuestionGroup(test_id=test.id, title="Passage 1", order_number=0)
    pg_session.add(group)
    pg_session.flush()
    question = Question(test_id=test.id, question_text="Q about the passage", question_type="single_choice", score=1, group_id=group.id)
    pg_session.add(question)
    pg_session.flush()

    reloaded = pg_session.query(Question).filter(Question.id == question.id).one()
    assert reloaded.group_id == group.id
    assert reloaded.test_id == test.id  # unchanged, still the question's own ownership


def test_deleting_question_group_sets_question_group_id_to_null(pg_session):
    test = _make_test(pg_session)
    group = QuestionGroup(test_id=test.id, title="Passage 1", order_number=0)
    pg_session.add(group)
    pg_session.flush()
    question = Question(test_id=test.id, question_text="Q", question_type="single_choice", score=1, group_id=group.id)
    pg_session.add(question)
    pg_session.flush()

    pg_session.delete(group)
    pg_session.commit()

    reloaded = pg_session.query(Question).filter(Question.id == question.id).one()
    assert reloaded.group_id is None
    assert reloaded.test_id == test.id  # the question itself is NOT deleted


# --- Test.exam_variant: nullable, persists ---

def test_exam_variant_nullable(pg_session):
    test = _make_test(pg_session)
    reloaded = pg_session.query(Test).filter(Test.id == test.id).one()
    assert reloaded.exam_variant is None


def test_exam_variant_persists(pg_session):
    subject = Subject(name=f"Subject-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="IELTS Academic", duration=60, question_count=0, status="published", exam_variant="Academic")
    pg_session.add(test)
    pg_session.commit()

    reloaded = pg_session.query(Test).filter(Test.id == test.id).one()
    assert reloaded.exam_variant == "Academic"


# --- ResultSection: creation, relations, UNIQUE(result_id, section_id) ---

def test_result_section_creation_and_relations(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    section = ExamSection(test_id=test.id, name="Listening", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    attempt = TestAttempt(user_id=student_id, test_id=test.id, status=AttemptStatus.SUBMITTED, start_time=datetime.now(timezone.utc))
    pg_session.add(attempt)
    pg_session.flush()
    result = Result(attempt_id=attempt.id, user_id=student_id, test_id=test.id, score=8.0, percentage=80.0)
    pg_session.add(result)
    pg_session.flush()

    result_section = ResultSection(result_id=result.id, section_id=section.id, raw_score=32.0, scaled_score=8.0)
    pg_session.add(result_section)
    pg_session.flush()

    reloaded = pg_session.query(ResultSection).filter(ResultSection.id == result_section.id).one()
    assert reloaded.result_id == result.id
    assert reloaded.section_id == section.id
    assert float(reloaded.raw_score) == 32.0
    assert float(reloaded.scaled_score) == 8.0


def test_unique_result_id_section_id_enforced(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    section = ExamSection(test_id=test.id, name="Listening", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    attempt = TestAttempt(user_id=student_id, test_id=test.id, status=AttemptStatus.SUBMITTED, start_time=datetime.now(timezone.utc))
    pg_session.add(attempt)
    pg_session.flush()
    result = Result(attempt_id=attempt.id, user_id=student_id, test_id=test.id, score=8.0, percentage=80.0)
    pg_session.add(result)
    pg_session.flush()

    pg_session.add(ResultSection(result_id=result.id, section_id=section.id, raw_score=32.0))
    pg_session.flush()

    pg_session.add(ResultSection(result_id=result.id, section_id=section.id, raw_score=30.0))
    try:
        pg_session.flush()
        assert False, "expected IntegrityError from UNIQUE(result_id, section_id)"
    except IntegrityError:
        pg_session.rollback()


# --- Backward compatibility: existing Result/Question remain valid ---

def test_existing_result_remains_valid_without_result_section(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    attempt = TestAttempt(user_id=student_id, test_id=test.id, status=AttemptStatus.SUBMITTED, start_time=datetime.now(timezone.utc))
    pg_session.add(attempt)
    pg_session.flush()
    result = Result(attempt_id=attempt.id, user_id=student_id, test_id=test.id, score=75.0, percentage=75.0, is_passed=True)
    pg_session.add(result)
    pg_session.commit()

    reloaded = pg_session.query(Result).filter(Result.id == result.id).one()
    assert float(reloaded.score) == 75.0
    assert reloaded.is_passed is True
    sections = pg_session.query(ResultSection).filter(ResultSection.result_id == result.id).all()
    assert sections == []


def test_existing_question_remains_valid_without_question_group(pg_session):
    test = _make_test(pg_session)
    question = Question(test_id=test.id, question_text="Plain question", question_type="single_choice", score=1)
    pg_session.add(question)
    pg_session.commit()

    reloaded = pg_session.query(Question).filter(Question.id == question.id).one()
    assert reloaded.group_id is None
    assert reloaded.question_text == "Plain question"
