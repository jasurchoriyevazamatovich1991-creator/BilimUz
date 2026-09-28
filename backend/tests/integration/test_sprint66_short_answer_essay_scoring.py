"""
Sprint 66 — Short Answer / Essay Scoring Correctness Fix. Integration
tests against real PostgreSQL (Sprint 40's pg_session infrastructure),
following the direct-service-call pattern established by Sprint 61's
own scoring-scope tests (test_sprint61_finalization_scoring_scope.py).

Sprint 65 audit finding (HIGH severity, candidate C1): short_answer and
essay questions had Answer.text_answer sitting completely unused end to
end (no request-schema field, no persistence, no scoring awareness).
Because is_correct stayed NULL forever for them, PercentageScoringStrategy
.calculate() still summed their question.score into total_possible while
they could never contribute to total_score — silently deflating the
automatic percentage of any exam containing one.

Fix (Option A from the Sprint 66 prompt — a scoring-correctness fix, NOT
manual grading):
  - SaveAnswerRequest gained an additive text_answer field (schemas.py).
  - AttemptService.save_answer() now has a branch for any question whose
    question_type is NOT in scoring.AUTO_GRADABLE_QUESTION_TYPES
    ({single_choice, multiple_choice, true_false}): it upserts
    {"text_answer": ..., "is_correct": None} via the existing, fully
    generic AnswerRepository.upsert() and returns — no new persistence
    mechanism, no new endpoint.
  - AttemptService._finalize() now filters the (already effective/
    modular-aware, per Sprint 61/63) question list down to
    AUTO_GRADABLE_QUESTION_TYPES before calling
    DEFAULT_SCORING_STRATEGY.calculate() — so short_answer/essay can
    never appear in the automatic total_possible.
  - AttemptService._build_result() is deliberately UNCHANGED: it already
    only counts is_correct is True answers, and short_answer/essay
    always have is_correct=None, so correct_count was never affected.
    total_questions still means "all effective exam questions" — a
    documented, deliberate semantic limitation (see service.py comment),
    not a bug this sprint fixes.

These tests exercise the production request -> service -> repository ->
scoring flow directly through AttemptService (matching every other
attempts-module integration test in this project), not a separate
fake-repository mechanism.
"""
import uuid

import pytest

from app.modules.attempts.exceptions import AttemptNotFoundException
from app.modules.attempts.models import Answer, AttemptModuleProgress, AttemptStatus
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
    user = User(role_id=role.id, first_name="F66", last_name="X", email=f"f66-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    pg_session.flush()
    return user.id


def _make_service(pg_session) -> AttemptService:
    """Production-realistic construction — module_execution/module_repo
    always wired, matching get_attempt_service()'s real FastAPI DI."""
    return AttemptService(
        AttemptRepository(pg_session), AnswerRepository(pg_session), TestRepository(pg_session),
        QuestionRepository(pg_session), OptionRepository(pg_session),
        ModuleExecutionService(
            ExamModuleRepository(pg_session), AttemptModuleProgressRepository(pg_session),
            QuestionRepository(pg_session), AnswerRepository(pg_session), AttemptRepository(pg_session),
        ),
        ExamModuleRepository(pg_session),
    )


def _make_test(pg_session, title="Sprint66 Test") -> Test:
    subject = Subject(name=f"S66-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title=title, duration=120, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    return test


def _make_choice_question(pg_session, test_id, module_id=None, score=1, question_type="single_choice") -> tuple[Question, QuestionOption]:
    q = Question(test_id=test_id, question_text="Q", question_type=question_type, score=score, module_id=module_id)
    pg_session.add(q)
    pg_session.flush()
    correct = QuestionOption(question_id=q.id, option_text="A", is_correct=True)
    wrong = QuestionOption(question_id=q.id, option_text="B", is_correct=False)
    pg_session.add_all([correct, wrong])
    pg_session.flush()
    return q, correct


def _make_text_question(pg_session, test_id, module_id=None, score=1, question_type="short_answer") -> Question:
    q = Question(test_id=test_id, question_text="Free text Q", question_type=question_type, score=score, module_id=module_id)
    pg_session.add(q)
    pg_session.flush()
    return q


def _get_answer(pg_session, attempt_id, question_id) -> Answer:
    return pg_session.query(Answer).filter(Answer.attempt_id == attempt_id, Answer.question_id == question_id).one()


# --- Tests 1-4: text_answer accepted + persisted for short_answer / essay ---

def test_text_answer_accepted_and_persisted_for_short_answer(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    q = _make_text_question(pg_session, test.id, question_type="short_answer")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    service.save_answer(attempt.id, student_id, q.id, selected_option=None, text_answer="Newton's second law")
    pg_session.commit()

    answer = _get_answer(pg_session, attempt.id, q.id)
    assert answer.text_answer == "Newton's second law"
    assert answer.is_correct is None


def test_text_answer_accepted_and_persisted_for_essay(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    q = _make_text_question(pg_session, test.id, question_type="essay")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    essay_text = "A long-form essay answer discussing the causes of..."
    service.save_answer(attempt.id, student_id, q.id, selected_option=None, text_answer=essay_text)
    pg_session.commit()

    answer = _get_answer(pg_session, attempt.id, q.id)
    assert answer.text_answer == essay_text
    assert answer.is_correct is None


def test_text_answer_upsert_overwrites_previous_value(pg_session):
    """Auto-save semantics (PATCH, safe to call repeatedly) must hold for
    free-text answers exactly as for choice answers."""
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    q = _make_text_question(pg_session, test.id, question_type="short_answer")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    service.save_answer(attempt.id, student_id, q.id, selected_option=None, text_answer="draft one")
    pg_session.commit()
    service.save_answer(attempt.id, student_id, q.id, selected_option=None, text_answer="final answer")
    pg_session.commit()

    answer = _get_answer(pg_session, attempt.id, q.id)
    assert answer.text_answer == "final answer"

    all_answers = pg_session.query(Answer).filter(Answer.attempt_id == attempt.id, Answer.question_id == q.id).all()
    assert len(all_answers) == 1  # upsert, not a duplicate row


def test_essay_text_answer_persisted_independently_of_short_answer(pg_session):
    """Both free-text types share the same code path — verify neither
    interferes with the other within the same attempt."""
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    q_sa = _make_text_question(pg_session, test.id, question_type="short_answer")
    q_es = _make_text_question(pg_session, test.id, question_type="essay")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    service.save_answer(attempt.id, student_id, q_sa.id, selected_option=None, text_answer="short one")
    pg_session.commit()
    service.save_answer(attempt.id, student_id, q_es.id, selected_option=None, text_answer="essay one")
    pg_session.commit()

    assert _get_answer(pg_session, attempt.id, q_sa.id).text_answer == "short one"
    assert _get_answer(pg_session, attempt.id, q_es.id).text_answer == "essay one"


# --- Tests 5-6: short_answer / essay excluded from automatic denominator ---

def test_short_answer_excluded_from_automatic_denominator(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    q_choice, opt_correct = _make_choice_question(pg_session, test.id, score=1)
    q_sa = _make_text_question(pg_session, test.id, score=1, question_type="short_answer")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    service.save_answer(attempt.id, student_id, q_choice.id, selected_option=opt_correct.id)
    pg_session.commit()
    service.save_answer(attempt.id, student_id, q_sa.id, selected_option=None, text_answer="an answer")
    pg_session.commit()

    result = service.submit_attempt(attempt.id, student_id)
    pg_session.commit()

    # Denominator is 1 (only the choice question) -> 100%, not 50%.
    assert result.percentage == 100.0
    assert result.score == 1.0


def test_essay_excluded_from_automatic_denominator(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    q_choice, opt_correct = _make_choice_question(pg_session, test.id, score=1)
    q_es = _make_text_question(pg_session, test.id, score=1, question_type="essay")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    service.save_answer(attempt.id, student_id, q_choice.id, selected_option=opt_correct.id)
    pg_session.commit()
    service.save_answer(attempt.id, student_id, q_es.id, selected_option=None, text_answer="an essay")
    pg_session.commit()

    result = service.submit_attempt(attempt.id, student_id)
    pg_session.commit()

    assert result.percentage == 100.0
    assert result.score == 1.0


# --- Tests 7-9: existing choice-type scoring unchanged ---

def test_single_choice_scoring_unchanged(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    q1, opt1 = _make_choice_question(pg_session, test.id, score=1, question_type="single_choice")
    q2, opt2 = _make_choice_question(pg_session, test.id, score=1, question_type="single_choice")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()
    service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()
    # q2 left unanswered -> wrong, exactly as before Sprint 66

    result = service.submit_attempt(attempt.id, student_id)
    pg_session.commit()

    assert result.total_questions == 2
    assert result.correct_count == 1
    assert result.percentage == 50.0


def test_multiple_choice_scoring_unchanged(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    q = Question(test_id=test.id, question_text="MC", question_type="multiple_choice", score=2)
    pg_session.add(q)
    pg_session.flush()
    opt_a = QuestionOption(question_id=q.id, option_text="A", is_correct=True)
    opt_b = QuestionOption(question_id=q.id, option_text="B", is_correct=True)
    opt_c = QuestionOption(question_id=q.id, option_text="C", is_correct=False)
    pg_session.add_all([opt_a, opt_b, opt_c])
    pg_session.flush()
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()
    service.save_answer(attempt.id, student_id, q.id, selected_option=None, selected_options=[opt_a.id, opt_b.id])
    pg_session.commit()

    result = service.submit_attempt(attempt.id, student_id)
    pg_session.commit()

    assert result.total_questions == 1
    assert result.correct_count == 1
    assert result.percentage == 100.0

    answer = _get_answer(pg_session, attempt.id, q.id)
    assert answer.is_correct is True
    assert set(answer.selected_options) == {opt_a.id, opt_b.id}


def test_true_false_scoring_unchanged(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    q, opt_true = _make_choice_question(pg_session, test.id, score=1, question_type="true_false")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()
    service.save_answer(attempt.id, student_id, q.id, selected_option=opt_true.id)
    pg_session.commit()

    result = service.submit_attempt(attempt.id, student_id)
    pg_session.commit()

    assert result.total_questions == 1
    assert result.correct_count == 1
    assert result.percentage == 100.0


# --- Test 10: mixed auto-scored + short_answer/essay (the prompt's worked example) ---

def test_mixed_auto_scored_and_free_text_scoring(pg_session):
    """Exactly the Sprint 66 prompt's worked example: 2 correct
    single_choice + short_answer + essay -> denominator is 2, not 4."""
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    q1, opt1 = _make_choice_question(pg_session, test.id, score=1, question_type="single_choice")
    q2, opt2 = _make_choice_question(pg_session, test.id, score=1, question_type="single_choice")
    q3 = _make_text_question(pg_session, test.id, score=1, question_type="short_answer")
    q4 = _make_text_question(pg_session, test.id, score=1, question_type="essay")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()
    service.save_answer(attempt.id, student_id, q2.id, selected_option=opt2.id)
    pg_session.commit()
    service.save_answer(attempt.id, student_id, q3.id, selected_option=None, text_answer="answered")
    pg_session.commit()
    service.save_answer(attempt.id, student_id, q4.id, selected_option=None, text_answer="answered")
    pg_session.commit()

    result = service.submit_attempt(attempt.id, student_id)
    pg_session.commit()

    assert result.score == 2.0
    assert result.percentage == 100.0  # 2/2, NOT 2/4 (50%)
    # total_questions is documented to remain "all effective exam
    # questions" (4), a deliberate, out-of-scope-to-change semantic
    # limitation — see service.py's _build_result() comment.
    assert result.total_questions == 4
    assert result.correct_count == 2


# --- Test 11: modular effective-question scoring compatibility ---

def test_modular_effective_question_scoring_excludes_free_text(pg_session):
    """Sprint 61/63's effective-question-set algorithm must still run
    first; the Sprint 66 auto-gradable filter is then applied on top of
    its output, not instead of it. Module 2 (short_answer) is answered
    and submitted like any other module."""
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S66-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Sprint66 Modular", duration=120, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    module2 = ExamModule(section_id=section.id, name="Module 2", order_number=1)
    pg_session.add_all([module1, module2])
    pg_session.flush()

    q1, opt1 = _make_choice_question(pg_session, test.id, module_id=module1.id, score=1, question_type="single_choice")
    q2 = _make_text_question(pg_session, test.id, module_id=module2.id, score=1, question_type="short_answer")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)  # module1's progress row only
    pg_session.commit()

    service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()
    outcome1 = service.submit_module(attempt.id, module1.id, student_id)
    pg_session.commit()
    assert outcome1["completed"] is False
    assert outcome1["next_module_id"] == module2.id

    service.save_answer(attempt.id, student_id, q2.id, selected_option=None, text_answer="my free text answer")
    pg_session.commit()
    outcome2 = service.submit_module(attempt.id, module2.id, student_id)
    pg_session.commit()

    assert outcome2["completed"] is True
    result = outcome2["result"]
    # Effective question set (Sprint 61) = {q1, q2}; auto-gradable filter
    # (Sprint 66) narrows scoring to {q1} only -> 1/1 = 100%, not 1/2.
    assert result.percentage == 100.0
    assert result.score == 1.0
    assert result.total_questions == 2  # unchanged effective-set count (documented limitation)

    answer = _get_answer(pg_session, attempt.id, q2.id)
    assert answer.text_answer == "my free text answer"
    assert answer.is_correct is None


# --- Test 12: unanswered short_answer/essay do not reduce automatic score ---

def test_unanswered_short_answer_and_essay_do_not_reduce_score(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    q1, opt1 = _make_choice_question(pg_session, test.id, score=1, question_type="single_choice")
    _make_text_question(pg_session, test.id, score=1, question_type="short_answer")  # left unanswered
    _make_text_question(pg_session, test.id, score=1, question_type="essay")  # left unanswered
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()
    # short_answer/essay never answered at all -> no Answer row for them.

    result = service.submit_attempt(attempt.id, student_id)
    pg_session.commit()

    assert result.percentage == 100.0  # 1/1, unaffected by the two unanswered free-text questions
    assert result.score == 1.0


# --- Edge case F: short_answer + essay only -> automatic denominator is zero ---

def test_free_text_only_uses_existing_zero_denominator_convention(pg_session):
    """PercentageScoringStrategy.calculate() already has an `or 1.0`
    fallback for an empty total_possible (pre-existing convention, not
    invented by this sprint) — verify that convention still applies when
    EVERY question is short_answer/essay (auto-gradable set is empty)."""
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    q_sa = _make_text_question(pg_session, test.id, score=1, question_type="short_answer")
    q_es = _make_text_question(pg_session, test.id, score=1, question_type="essay")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    service.save_answer(attempt.id, student_id, q_sa.id, selected_option=None, text_answer="a")
    pg_session.commit()
    service.save_answer(attempt.id, student_id, q_es.id, selected_option=None, text_answer="b")
    pg_session.commit()

    result = service.submit_attempt(attempt.id, student_id)
    pg_session.commit()

    assert result.score == 0.0
    assert result.percentage == 0.0  # 0 / 1.0 (existing fallback denominator), not a crash or NaN
    assert result.total_questions == 2


# --- Security/ownership regression: save_answer still enforces attempt ownership ---

def test_save_answer_still_enforces_attempt_ownership(pg_session):
    """The answer request schema/service were touched this sprint
    (text_answer added) — prove _get_owned_attempt()'s existing
    ownership check is completely unaffected, for both a free-text
    question and an auto-graded one."""
    owner_id = _make_student(pg_session)
    other_student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    q_choice, opt_correct = _make_choice_question(pg_session, test.id, score=1)
    q_text = _make_text_question(pg_session, test.id, score=1, question_type="short_answer")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, owner_id)
    pg_session.commit()

    with pytest.raises(AttemptNotFoundException):
        service.save_answer(attempt.id, other_student_id, q_choice.id, selected_option=opt_correct.id)

    with pytest.raises(AttemptNotFoundException):
        service.save_answer(attempt.id, other_student_id, q_text.id, selected_option=None, text_answer="hijacked")

    # Confirm nothing was persisted by the rejected attempts.
    assert pg_session.query(Answer).filter(Answer.attempt_id == attempt.id).count() == 0
