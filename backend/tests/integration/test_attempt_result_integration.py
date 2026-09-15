"""
Sprint 40 Phase 3 — Integration Test 3: Test Attempt / Result, and
Question -> Test -> Attempt relational integrity, against real
PostgreSQL. Uses ONLY existing models/services — no invented scoring
rules, no invented endpoints.
"""
import uuid

from app.modules.attempts.models import Answer, TestAttempt
from app.modules.attempts.repository import AnswerRepository, AttemptRepository
from app.modules.attempts.service import AttemptService
from app.modules.questions.models import Question, QuestionOption
from app.modules.questions.repository import OptionRepository, QuestionRepository
from app.modules.results.models import Result
from app.modules.results.repository import ResultRepository, StatisticsRepository
from app.modules.results.service import ResultService
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import Test, TestStatus
from app.modules.tests.repository import TestRepository
from app.modules.users.models import User, UserStatus


def _make_student(pg_session) -> uuid.UUID:
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(
        role_id=role.id, first_name="Integration", last_name="Student",
        email=f"student-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE,
    )
    pg_session.add(user)
    pg_session.flush()
    return user.id


def _make_published_test_with_two_single_choice_questions(pg_session) -> Test:
    """Test → Question → QuestionOption relational chain, minimum valid
    real rows for a 2-question, single_choice, 50%-passing test."""
    subject = Subject(name=f"Integration Subject {uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()

    test = Test(
        subject_id=subject.id, title="Integration Test", duration=30,
        question_count=2, passing_score=50, status=TestStatus.PUBLISHED,
        shuffle_questions=False, shuffle_answers=False,
    )
    pg_session.add(test)
    pg_session.flush()

    for i in range(2):
        question = Question(test_id=test.id, question_text=f"Savol {i}?", question_type="single_choice", score=1)
        pg_session.add(question)
        pg_session.flush()
        correct = QuestionOption(question_id=question.id, option_text="To'g'ri", is_correct=True)
        wrong = QuestionOption(question_id=question.id, option_text="Noto'g'ri", is_correct=False)
        pg_session.add_all([correct, wrong])
        pg_session.flush()

    return test


def _attempt_service(pg_session) -> AttemptService:
    return AttemptService(
        AttemptRepository(pg_session), AnswerRepository(pg_session), TestRepository(pg_session),
        QuestionRepository(pg_session), OptionRepository(pg_session),
    )


def _result_service(pg_session) -> ResultService:
    return ResultService(
        ResultRepository(pg_session), StatisticsRepository(pg_session), AttemptRepository(pg_session),
        AnswerRepository(pg_session), TestRepository(pg_session), QuestionRepository(pg_session),
    )


def test_full_attempt_submit_and_result_flow_persists_to_real_postgres(pg_session):
    """The end-to-end flow: start attempt -> answer all questions
    correctly -> submit -> create result. Verifies the EXISTING scoring
    behavior (100% for all-correct) against real persisted rows, not a
    mock."""
    student_id = _make_student(pg_session)
    test = _make_published_test_with_two_single_choice_questions(pg_session)
    attempt_service = _attempt_service(pg_session)
    result_service = _result_service(pg_session)

    attempt = attempt_service.start_attempt(test.id, student_id)
    assert attempt.question_order is not None
    assert len(attempt.question_order) == 2

    # Answer every question with its correct option.
    for question_id in attempt.question_order:
        correct_option = pg_session.query(QuestionOption).filter(
            QuestionOption.question_id == question_id, QuestionOption.is_correct.is_(True),
        ).one()
        attempt_service.save_answer(attempt.id, student_id, question_id, correct_option.id)

    submit_result = attempt_service.submit_attempt(attempt.id, student_id)
    assert submit_result.score == 2
    assert float(submit_result.percentage) == 100.0

    # Re-fetch the TestAttempt from a FRESH query — proves the score is
    # actually in the real table, not just returned in-memory.
    reloaded_attempt = pg_session.query(TestAttempt).filter(TestAttempt.id == attempt.id).one()
    assert reloaded_attempt.status == "submitted"
    assert reloaded_attempt.finish_time is not None
    assert float(reloaded_attempt.score) == 2.0

    result = result_service.create_result(attempt.id, student_id)
    reloaded_result = pg_session.query(Result).filter(Result.id == result.id).one()
    assert reloaded_result.is_passed is True  # 100% >= 50% passing_score
    assert float(reloaded_result.percentage) == 100.0


def test_answers_persist_with_correct_is_correct_flag(pg_session):
    """Question -> Test -> Attempt -> Answer relational integrity: one
    correct, one incorrect answer, verified via a fresh query joining
    back through the real foreign keys."""
    student_id = _make_student(pg_session)
    test = _make_published_test_with_two_single_choice_questions(pg_session)
    attempt_service = _attempt_service(pg_session)

    attempt = attempt_service.start_attempt(test.id, student_id)
    q1, q2 = attempt.question_order

    correct_for_q1 = pg_session.query(QuestionOption).filter(QuestionOption.question_id == q1, QuestionOption.is_correct.is_(True)).one()
    wrong_for_q2 = pg_session.query(QuestionOption).filter(QuestionOption.question_id == q2, QuestionOption.is_correct.is_(False)).one()

    attempt_service.save_answer(attempt.id, student_id, q1, correct_for_q1.id)
    attempt_service.save_answer(attempt.id, student_id, q2, wrong_for_q2.id)

    answers = {a.question_id: a for a in pg_session.query(Answer).filter(Answer.attempt_id == attempt.id).all()}
    assert answers[q1].is_correct is True
    assert answers[q2].is_correct is False

    submit_result = attempt_service.submit_attempt(attempt.id, student_id)
    assert submit_result.score == 1
    assert float(submit_result.percentage) == 50.0


def test_unanswered_question_is_scored_as_incorrect_not_silently_ignored(pg_session):
    student_id = _make_student(pg_session)
    test = _make_published_test_with_two_single_choice_questions(pg_session)
    attempt_service = _attempt_service(pg_session)

    attempt = attempt_service.start_attempt(test.id, student_id)
    q1 = attempt.question_order[0]
    correct = pg_session.query(QuestionOption).filter(QuestionOption.question_id == q1, QuestionOption.is_correct.is_(True)).one()
    attempt_service.save_answer(attempt.id, student_id, q1, correct.id)
    # Second question deliberately left unanswered.

    submit_result = attempt_service.submit_attempt(attempt.id, student_id)
    assert submit_result.score == 1
    assert float(submit_result.percentage) == 50.0


def test_result_is_not_passed_when_below_passing_score(pg_session):
    student_id = _make_student(pg_session)
    test = _make_published_test_with_two_single_choice_questions(pg_session)  # passing_score=50
    attempt_service = _attempt_service(pg_session)
    result_service = _result_service(pg_session)

    attempt = attempt_service.start_attempt(test.id, student_id)
    q1 = attempt.question_order[0]
    wrong = pg_session.query(QuestionOption).filter(QuestionOption.question_id == q1, QuestionOption.is_correct.is_(False)).one()
    attempt_service.save_answer(attempt.id, student_id, q1, wrong.id)
    attempt_service.submit_attempt(attempt.id, student_id)

    result = result_service.create_result(attempt.id, student_id)
    assert result.is_passed is False  # 0% < 50%
