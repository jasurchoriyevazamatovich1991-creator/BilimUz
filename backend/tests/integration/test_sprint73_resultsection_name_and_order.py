"""
Sprint 73 — RS-FE-1, against real PostgreSQL. Matches the established
style for this subsystem (test_sprint72_resultsection_scoring_scope.py).

Confirms ResultSectionOut now carries `name`/`order_number` (populated
from the owning ExamSection), in the correct order, through the full
create_result() -> get_result_detail() path — the backend half of
exposing section-level results to the frontend (the frontend half,
api/results.ts + ResultPage.tsx, has no backend-testable surface here).
"""
import uuid
from datetime import datetime, timezone

from app.modules.attempts.models import Answer, AttemptStatus, TestAttempt
from app.modules.attempts.repository import AnswerRepository, AttemptModuleProgressRepository, AttemptRepository
from app.modules.questions.models import Question, QuestionOption
from app.modules.questions.repository import OptionRepository, QuestionRepository
from app.modules.results.repository import ResultRepository, ResultSectionRepository, StatisticsRepository
from app.modules.results.service import ResultService
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import ExamSection, Test
from app.modules.tests.repository import ExamSectionRepository, TestRepository
from app.modules.users.models import User, UserStatus


def _make_student(pg_session, prefix: str) -> uuid.UUID:
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name=prefix, last_name="RSFE1", email=f"{prefix.lower()}-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    pg_session.flush()
    return user.id


def _make_result_service(pg_session) -> ResultService:
    return ResultService(
        ResultRepository(pg_session), StatisticsRepository(pg_session), AttemptRepository(pg_session),
        AnswerRepository(pg_session), TestRepository(pg_session), QuestionRepository(pg_session),
        ExamSectionRepository(pg_session), ResultSectionRepository(pg_session),
    )


def test_result_sections_expose_name_and_order_in_correct_sequence(pg_session):
    user_id = _make_student(pg_session, "RSFE1")
    subject = Subject(name=f"RSFE1Subj-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="RSFE1 Test", duration=60, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()

    # Deliberately created/added out of display order (Reading=1 before
    # Listening=0) so a naive "insertion order" bug would be caught.
    section_reading = ExamSection(test_id=test.id, name="Reading", order_number=1)
    section_listening = ExamSection(test_id=test.id, name="Listening", order_number=0)
    pg_session.add_all([section_reading, section_listening])
    pg_session.flush()

    q_listening = Question(test_id=test.id, question_text="L1", question_type="single_choice", score=5, section_id=section_listening.id)
    q_reading = Question(test_id=test.id, question_text="R1", question_type="single_choice", score=5, section_id=section_reading.id)
    pg_session.add_all([q_listening, q_reading])
    pg_session.flush()
    opt_l = QuestionOption(question_id=q_listening.id, option_text="A", is_correct=True)
    opt_r = QuestionOption(question_id=q_reading.id, option_text="A", is_correct=True)
    pg_session.add_all([opt_l, opt_r])
    pg_session.flush()

    now = datetime.now(timezone.utc)
    attempt = TestAttempt(
        test_id=test.id, user_id=user_id, status=AttemptStatus.SUBMITTED,
        start_time=now, finish_time=now, question_order=[q_listening.id, q_reading.id],
    )
    pg_session.add(attempt)
    pg_session.flush()
    pg_session.add(Answer(attempt_id=attempt.id, question_id=q_listening.id, selected_option=opt_l.id, is_correct=True))
    pg_session.add(Answer(attempt_id=attempt.id, question_id=q_reading.id, selected_option=opt_r.id, is_correct=True))
    pg_session.commit()

    service = _make_result_service(pg_session)
    result = service.create_result(attempt.id, user_id)

    detail = service.get_result_detail(result.id, user_id)

    assert len(detail.sections) == 2
    # Ordered by ExamSection.order_number (Listening=0 before Reading=1),
    # NOT creation/insertion order.
    assert detail.sections[0].name == "Listening"
    assert detail.sections[0].order_number == 0
    assert detail.sections[0].raw_score == 5
    assert detail.sections[1].name == "Reading"
    assert detail.sections[1].order_number == 1
    assert detail.sections[1].raw_score == 5


def test_non_modular_result_still_has_empty_sections_list(pg_session):
    """Regression guard: a test with zero ExamSections must still
    produce sections=[] exactly as before this sprint — no name/
    order_number plumbing changes that."""
    user_id = _make_student(pg_session, "RSFE1B")
    subject = Subject(name=f"RSFE1BSubj-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="RSFE1B Test", duration=60, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()

    q = Question(test_id=test.id, question_text="Q1", question_type="single_choice", score=5)
    pg_session.add(q)
    pg_session.flush()
    opt = QuestionOption(question_id=q.id, option_text="A", is_correct=True)
    pg_session.add(opt)
    pg_session.flush()

    now = datetime.now(timezone.utc)
    attempt = TestAttempt(test_id=test.id, user_id=user_id, status=AttemptStatus.SUBMITTED, start_time=now, finish_time=now, question_order=[q.id])
    pg_session.add(attempt)
    pg_session.flush()
    pg_session.add(Answer(attempt_id=attempt.id, question_id=q.id, selected_option=opt.id, is_correct=True))
    pg_session.commit()

    service = _make_result_service(pg_session)
    result = service.create_result(attempt.id, user_id)
    detail = service.get_result_detail(result.id, user_id)

    assert detail.sections == []
