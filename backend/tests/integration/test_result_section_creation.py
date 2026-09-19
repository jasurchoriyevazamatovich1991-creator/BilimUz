"""
Sprint 54 — ResultSection + Modular Scoring Foundation, integration
tests against real PostgreSQL (Sprint 40's infrastructure — pg_session,
TEST_DATABASE_URL). Extends the existing attempt->result flow (see
tests/integration/test_attempt_result_integration.py, whose direct
service-call pattern this file reuses) with the new, additive
section-level scoring introduced this sprint.

No new endpoint exists for this sprint (per its explicit scope) — every
test here exercises ResultService.create_result() directly, exactly
the same way test_attempt_result_integration.py already does, since
that IS the one and only entry point this sprint changes. POST
/results itself is unmodified (same request/response shape), so there
is nothing new to test at the HTTP layer specifically.
"""
import threading
import uuid

from app.modules.attempts.models import Answer, TestAttempt
from app.modules.attempts.repository import AnswerRepository, AttemptRepository
from app.modules.attempts.service import AttemptService
from app.modules.questions.models import Question, QuestionOption
from app.modules.questions.repository import OptionRepository, QuestionRepository
from app.modules.results.exceptions import ResultNotFoundException
from app.modules.results.models import Result, ResultSection, Statistics
from app.modules.results.repository import ResultRepository, ResultSectionRepository, StatisticsRepository
from app.modules.results.service import ResultService
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import ExamSection, Test, TestStatus
from app.modules.tests.repository import ExamSectionRepository, TestRepository
from app.modules.users.models import User, UserStatus

import pytest


# --- Shared helpers ------------------------------------------------------

def _make_student(pg_session) -> uuid.UUID:
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(
        role_id=role.id, first_name="Sprint54", last_name="Student",
        email=f"s54-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE,
    )
    pg_session.add(user)
    pg_session.flush()
    return user.id


def _make_test(pg_session, max_attempts=None) -> Test:
    subject = Subject(name=f"Sprint54 Subject {uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(
        subject_id=subject.id, title="Sprint 54 Test", duration=60,
        question_count=0, status=TestStatus.PUBLISHED,
        shuffle_questions=False, shuffle_answers=False, max_attempts=max_attempts,
    )
    pg_session.add(test)
    pg_session.flush()
    return test


def _add_section_with_questions(pg_session, test: Test, order_number: int, count: int) -> ExamSection:
    section = ExamSection(test_id=test.id, name=f"Section-{order_number}", order_number=order_number)
    pg_session.add(section)
    pg_session.flush()
    for i in range(count):
        question = Question(
            test_id=test.id, question_text=f"Section {order_number} Q{i}",
            question_type="single_choice", score=1, section_id=section.id,
        )
        pg_session.add(question)
        pg_session.flush()
        correct = QuestionOption(question_id=question.id, option_text="Correct", is_correct=True)
        wrong = QuestionOption(question_id=question.id, option_text="Wrong", is_correct=False)
        pg_session.add_all([correct, wrong])
        pg_session.flush()
    return section


def _add_plain_questions(pg_session, test: Test, count: int) -> None:
    """No section_id — the non-modular case."""
    for i in range(count):
        question = Question(test_id=test.id, question_text=f"Plain Q{i}", question_type="single_choice", score=1)
        pg_session.add(question)
        pg_session.flush()
        correct = QuestionOption(question_id=question.id, option_text="Correct", is_correct=True)
        wrong = QuestionOption(question_id=question.id, option_text="Wrong", is_correct=False)
        pg_session.add_all([correct, wrong])
        pg_session.flush()


def _attempt_service(pg_session) -> AttemptService:
    return AttemptService(
        AttemptRepository(pg_session), AnswerRepository(pg_session), TestRepository(pg_session),
        QuestionRepository(pg_session), OptionRepository(pg_session),
    )


def _result_service(pg_session) -> ResultService:
    return ResultService(
        ResultRepository(pg_session), StatisticsRepository(pg_session), AttemptRepository(pg_session),
        AnswerRepository(pg_session), TestRepository(pg_session), QuestionRepository(pg_session),
        ExamSectionRepository(pg_session), ResultSectionRepository(pg_session),
    )


def _answer_questions(pg_session, attempt_service, attempt, student_id, question_ids, correct: bool) -> None:
    for question_id in question_ids:
        wanted = True if correct else False
        option = pg_session.query(QuestionOption).filter(
            QuestionOption.question_id == question_id, QuestionOption.is_correct.is_(wanted),
        ).first()
        attempt_service.save_answer(attempt.id, student_id, question_id, option.id)


def _question_ids_for_section(pg_session, section: ExamSection) -> list[uuid.UUID]:
    return [q.id for q in pg_session.query(Question).filter(Question.section_id == section.id).all()]


# --- A: single section -----------------------------------------------------

def test_single_section_creates_exactly_one_result_section(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    section = _add_section_with_questions(pg_session, test, order_number=0, count=3)
    pg_session.commit()

    attempt_service = _attempt_service(pg_session)
    result_service = _result_service(pg_session)

    attempt = attempt_service.start_attempt(test.id, student_id)
    _answer_questions(pg_session, attempt_service, attempt, student_id, attempt.question_order, correct=True)
    attempt_service.submit_attempt(attempt.id, student_id)

    result = result_service.create_result(attempt.id, student_id)

    sections = pg_session.query(ResultSection).filter(ResultSection.result_id == result.id).all()
    assert len(sections) == 1
    row = sections[0]
    assert row.result_id == result.id
    assert row.section_id == section.id
    assert float(row.raw_score) == 3.0  # 3 questions, all correct, score=1 each
    assert row.scaled_score is None


# --- B: multiple sections, independent scoring -----------------------------

def test_multiple_sections_each_scored_independently(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    section_a = _add_section_with_questions(pg_session, test, order_number=0, count=2)
    section_b = _add_section_with_questions(pg_session, test, order_number=1, count=2)
    pg_session.commit()

    attempt_service = _attempt_service(pg_session)
    result_service = _result_service(pg_session)

    attempt = attempt_service.start_attempt(test.id, student_id)
    a_ids = _question_ids_for_section(pg_session, section_a)
    b_ids = _question_ids_for_section(pg_session, section_b)

    # Section A: all correct. Section B: all wrong. Proves no cross-section
    # contamination — if scoring mixed the two sections' answers/questions,
    # these numbers would not come out independently.
    _answer_questions(pg_session, attempt_service, attempt, student_id, a_ids, correct=True)
    _answer_questions(pg_session, attempt_service, attempt, student_id, b_ids, correct=False)
    attempt_service.submit_attempt(attempt.id, student_id)

    result = result_service.create_result(attempt.id, student_id)
    sections = {rs.section_id: rs for rs in pg_session.query(ResultSection).filter(ResultSection.result_id == result.id).all()}

    assert len(sections) == 2
    assert float(sections[section_a.id].raw_score) == 2.0  # both correct
    assert float(sections[section_b.id].raw_score) == 0.0  # both wrong
    assert sections[section_a.id].scaled_score is None
    assert sections[section_b.id].scaled_score is None


# --- C: non-modular test -----------------------------------------------------

def test_non_modular_test_creates_zero_result_sections(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    _add_plain_questions(pg_session, test, count=2)
    pg_session.commit()

    attempt_service = _attempt_service(pg_session)
    result_service = _result_service(pg_session)

    attempt = attempt_service.start_attempt(test.id, student_id)
    _answer_questions(pg_session, attempt_service, attempt, student_id, attempt.question_order, correct=True)
    submit_result = attempt_service.submit_attempt(attempt.id, student_id)
    assert float(submit_result.percentage) == 100.0  # existing behavior unchanged

    result = result_service.create_result(attempt.id, student_id)
    sections = pg_session.query(ResultSection).filter(ResultSection.result_id == result.id).all()
    assert sections == []
    assert float(result.percentage) == 100.0


# --- D: idempotency (sequential) --------------------------------------------

def test_create_result_twice_is_idempotent_no_duplicate_sections(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    _add_section_with_questions(pg_session, test, order_number=0, count=2)
    pg_session.commit()

    attempt_service = _attempt_service(pg_session)
    result_service = _result_service(pg_session)

    attempt = attempt_service.start_attempt(test.id, student_id)
    _answer_questions(pg_session, attempt_service, attempt, student_id, attempt.question_order, correct=True)
    attempt_service.submit_attempt(attempt.id, student_id)

    first = result_service.create_result(attempt.id, student_id)
    second = result_service.create_result(attempt.id, student_id)

    assert first.id == second.id
    all_results = pg_session.query(Result).filter(Result.attempt_id == attempt.id).all()
    assert len(all_results) == 1
    all_sections = pg_session.query(ResultSection).filter(ResultSection.result_id == first.id).all()
    assert len(all_sections) == 1  # not duplicated by the second call


# --- E: concurrent Result creation (real PostgreSQL, real threads) --------

def test_concurrent_result_creation_is_race_safe():
    """Sprint 54 concurrency requirement — mirrors Sprint 50's own
    CRITICAL-1 regression test pattern exactly (see
    tests/integration/test_module_execution.py::test_concurrent_module_submit_is_race_safe).

    Deliberately does NOT use pg_session — pg_session's SAVEPOINT-based
    transaction never becomes visible to a genuinely separate database
    connection, so real row-lock contention can't be observed through
    it. This test manages its own sessions/threads end-to-end and
    cleans up afterward.

    Unlike the module-submit race (where the loser is REJECTED with an
    exception, because a module can only ever be submitted once),
    create_result() is designed to be idempotent: BOTH callers here are
    expected to return successfully, both with a valid Result — the
    second one just gets back the first one's already-committed row
    instead of raising. AttemptRepository.get_by_id_locked's real
    PostgreSQL row-lock (SELECT ... FOR UPDATE) is what makes this
    deterministic: the second thread blocks on the attempt row until
    the first commits, then its own existence check reliably finds the
    already-created Result.
    """
    from sqlalchemy.orm import sessionmaker
    from app.db.database import engine
    from app.modules.grades.models import Grade  # noqa: F401 — side-effect import, see docstring below
    from app.modules.topics.models import Topic  # noqa: F401

    Session = sessionmaker(bind=engine)

    def make_result_service(s):
        return ResultService(
            ResultRepository(s), StatisticsRepository(s), AttemptRepository(s),
            AnswerRepository(s), TestRepository(s), QuestionRepository(s),
            ExamSectionRepository(s), ResultSectionRepository(s),
        )

    def make_attempt_service(s):
        return AttemptService(
            AttemptRepository(s), AnswerRepository(s), TestRepository(s), QuestionRepository(s), OptionRepository(s),
        )

    setup = Session()
    try:
        role = setup.query(Role).filter(Role.name == "Student").one()
        user = User(role_id=role.id, first_name="CR", last_name="ST", email=f"crst-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
        setup.add(user)
        setup.flush()
        student_id = user.id

        subject = Subject(name=f"S-{uuid.uuid4()}")
        setup.add(subject)
        setup.flush()

        test = Test(subject_id=subject.id, title="Concurrent Result Test", duration=60, question_count=0, status="published")
        setup.add(test)
        setup.flush()

        section = ExamSection(test_id=test.id, name="Section", order_number=0)
        setup.add(section)
        setup.flush()

        question = Question(test_id=test.id, question_text="Q1", question_type="single_choice", score=1, section_id=section.id)
        setup.add(question)
        setup.flush()
        correct_option = QuestionOption(question_id=question.id, option_text="A", is_correct=True)
        setup.add(correct_option)
        setup.flush()

        attempt_service = make_attempt_service(setup)
        attempt = attempt_service.start_attempt(test.id, student_id)
        attempt_service.save_answer(attempt.id, student_id, question.id, correct_option.id)
        attempt_service.submit_attempt(attempt.id, student_id)

        attempt_id, test_id, section_id, subject_id, question_id = attempt.id, test.id, section.id, subject.id, question.id
        setup.commit()
    finally:
        setup.close()

    outcomes = {}

    def worker(name: str):
        s = Session()
        svc = make_result_service(s)
        try:
            r = svc.create_result(attempt_id, student_id)
            s.commit()
            outcomes[name] = ("OK", r.id)
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

    try:
        # Both callers succeed (create_result is idempotent-by-design,
        # not reject-the-loser like module submit) and agree on the
        # SAME Result id.
        assert all(r is not None and r[0] == "OK" for r in results), f"expected both OK, got {results}"
        assert results[0][1] == results[1][1], f"expected identical Result id, got {results}"

        verify = Session()
        try:
            all_results = verify.query(Result).filter(Result.attempt_id == attempt_id).all()
            assert len(all_results) == 1, "no IntegrityError leak, no duplicate Result row"

            all_sections = verify.query(ResultSection).filter(ResultSection.result_id == all_results[0].id).all()
            assert len(all_sections) == 1, "exactly one ResultSection, not duplicated by the race"
            assert all_sections[0].section_id == section_id
        finally:
            verify.close()
    finally:
        cleanup = Session()
        try:
            cleanup.query(ResultSection).filter(ResultSection.result_id.in_(
                [r.id for r in cleanup.query(Result).filter(Result.attempt_id == attempt_id).all()]
            )).delete(synchronize_session=False)
            cleanup.query(Result).filter(Result.attempt_id == attempt_id).delete()
            cleanup.query(Statistics).filter(Statistics.user_id == student_id).delete()
            cleanup.query(Answer).filter(Answer.attempt_id == attempt_id).delete()
            cleanup.query(TestAttempt).filter(TestAttempt.id == attempt_id).delete()
            cleanup.query(QuestionOption).filter(QuestionOption.question_id == question_id).delete()
            cleanup.query(Question).filter(Question.test_id == test_id).delete()
            cleanup.query(ExamSection).filter(ExamSection.id == section_id).delete()
            cleanup.query(Test).filter(Test.id == test_id).delete()
            cleanup.query(Subject).filter(Subject.id == subject_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()


# --- F: section ownership — never trust a section from another test -------

def test_result_section_never_created_for_a_section_from_another_test(pg_session):
    """Defense-in-depth check for ResultService._create_result_sections'
    own explicit `section.test_id != result.test_id` guard. In normal
    operation this can never actually happen (sections only ever come
    from ExamSectionRepository.list_for_test(attempt.test_id) — no
    client-supplied section_id exists anywhere in this flow), so this
    test proves the guard itself works by making the section repository
    return a foreign-test section, standing in for 'assume the data
    feeding this method could be wrong, and verify the service still
    refuses to cross test boundaries' rather than trusting the DB FK
    alone."""
    student_id = _make_student(pg_session)
    test_a = _make_test(pg_session)
    _add_section_with_questions(pg_session, test_a, order_number=0, count=1)

    test_b = _make_test(pg_session)
    foreign_section = _add_section_with_questions(pg_session, test_b, order_number=0, count=1)
    pg_session.commit()

    attempt_service = _attempt_service(pg_session)
    result_service = _result_service(pg_session)

    attempt = attempt_service.start_attempt(test_a.id, student_id)
    _answer_questions(pg_session, attempt_service, attempt, student_id, attempt.question_order, correct=True)
    attempt_service.submit_attempt(attempt.id, student_id)

    # Simulate a compromised/buggy section lookup returning a section
    # that belongs to a DIFFERENT test than the attempt being resulted.
    original_list_for_test = result_service.section_repo.list_for_test
    result_service.section_repo.list_for_test = lambda test_id: [foreign_section]
    try:
        result = result_service.create_result(attempt.id, student_id)
    finally:
        result_service.section_repo.list_for_test = original_list_for_test

    sections = pg_session.query(ResultSection).filter(ResultSection.result_id == result.id).all()
    assert sections == [], "a section belonging to another test must never produce a ResultSection here"


# --- G: user ownership / IDOR ------------------------------------------------

def test_other_user_cannot_create_result_for_someone_elses_attempt(pg_session):
    owner_id = _make_student(pg_session)
    other_id = _make_student(pg_session)
    test = _make_test(pg_session)
    _add_section_with_questions(pg_session, test, order_number=0, count=1)
    pg_session.commit()

    attempt_service = _attempt_service(pg_session)
    result_service = _result_service(pg_session)

    attempt = attempt_service.start_attempt(test.id, owner_id)
    _answer_questions(pg_session, attempt_service, attempt, owner_id, attempt.question_order, correct=True)
    attempt_service.submit_attempt(attempt.id, owner_id)

    with pytest.raises(ResultNotFoundException):
        result_service.create_result(attempt.id, other_id)

    assert pg_session.query(Result).filter(Result.attempt_id == attempt.id).all() == []


# --- H: multiple attempts, same user, same test -----------------------------

def test_multiple_attempts_get_separate_results_and_sections(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session, max_attempts=2)
    section = _add_section_with_questions(pg_session, test, order_number=0, count=2)
    pg_session.commit()

    attempt_service = _attempt_service(pg_session)
    result_service = _result_service(pg_session)

    attempt_1 = attempt_service.start_attempt(test.id, student_id)
    _answer_questions(pg_session, attempt_service, attempt_1, student_id, attempt_1.question_order, correct=True)
    attempt_service.submit_attempt(attempt_1.id, student_id)
    result_1 = result_service.create_result(attempt_1.id, student_id)

    attempt_2 = attempt_service.start_attempt(test.id, student_id)
    _answer_questions(pg_session, attempt_service, attempt_2, student_id, attempt_2.question_order, correct=False)
    attempt_service.submit_attempt(attempt_2.id, student_id)
    result_2 = result_service.create_result(attempt_2.id, student_id)

    assert result_1.id != result_2.id
    all_results = pg_session.query(Result).filter(Result.user_id == student_id, Result.test_id == test.id).all()
    assert len(all_results) == 2

    sections_1 = pg_session.query(ResultSection).filter(ResultSection.result_id == result_1.id).all()
    sections_2 = pg_session.query(ResultSection).filter(ResultSection.result_id == result_2.id).all()
    assert len(sections_1) == 1 and len(sections_2) == 1
    assert float(sections_1[0].raw_score) == 2.0  # attempt 1: all correct
    assert float(sections_2[0].raw_score) == 0.0  # attempt 2: all wrong
    assert sections_1[0].section_id == section.id == sections_2[0].section_id


# --- I: question filtering (explicit, beyond test B) ------------------------

def test_section_scoring_never_counts_the_other_sections_questions(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    section_a = _add_section_with_questions(pg_session, test, order_number=0, count=3)
    section_b = _add_section_with_questions(pg_session, test, order_number=1, count=1)
    pg_session.commit()

    attempt_service = _attempt_service(pg_session)
    result_service = _result_service(pg_session)

    attempt = attempt_service.start_attempt(test.id, student_id)
    a_ids = _question_ids_for_section(pg_session, section_a)
    b_ids = _question_ids_for_section(pg_session, section_b)
    _answer_questions(pg_session, attempt_service, attempt, student_id, a_ids, correct=True)
    _answer_questions(pg_session, attempt_service, attempt, student_id, b_ids, correct=True)
    attempt_service.submit_attempt(attempt.id, student_id)

    result = result_service.create_result(attempt.id, student_id)
    sections = {rs.section_id: rs for rs in pg_session.query(ResultSection).filter(ResultSection.result_id == result.id).all()}

    # Section A has 3 questions worth 1 point each; if Section B's
    # single question ever leaked in, raw_score would be 4.0, not 3.0.
    assert float(sections[section_a.id].raw_score) == 3.0
    assert float(sections[section_b.id].raw_score) == 1.0


# --- J: scaled_score is always NULL -----------------------------------------

def test_scaled_score_is_always_null_on_creation(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    _add_section_with_questions(pg_session, test, order_number=0, count=1)
    _add_section_with_questions(pg_session, test, order_number=1, count=1)
    pg_session.commit()

    attempt_service = _attempt_service(pg_session)
    result_service = _result_service(pg_session)

    attempt = attempt_service.start_attempt(test.id, student_id)
    _answer_questions(pg_session, attempt_service, attempt, student_id, attempt.question_order, correct=True)
    attempt_service.submit_attempt(attempt.id, student_id)

    result = result_service.create_result(attempt.id, student_id)
    sections = pg_session.query(ResultSection).filter(ResultSection.result_id == result.id).all()
    assert len(sections) == 2
    assert all(s.scaled_score is None for s in sections)
