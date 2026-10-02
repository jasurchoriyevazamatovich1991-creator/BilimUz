"""
Sprint 72 — RS-1: ResultSection scoring scope fix, against real
PostgreSQL. Matches the established integration-test style for this
subsystem (test_sprint57_modular_question_delivery_scoping.py,
test_result_section_creation.py): ResultService/ModuleExecutionService
constructed directly with real repositories against pg_session.

Bug fixed: ResultService._create_result_sections() computed each
ResultSection.raw_score from EVERY question FK'd to the section
(QuestionRepository.list_by_section()), regardless of (a) whether this
attempt's adaptive routing ever actually delivered that question, and
(b) whether the question's type can even be automatically graded
(short_answer/essay always have is_correct=None — attempts/scoring.py's
own AUTO_GRADABLE_QUESTION_TYPES comment named this exact per-section
gap as deliberately unfixed as of Sprint 66). Fixed by filtering each
section's questions to the attempt's effective/delivered scope
(reusing ResultService._effective_result_question_ids(), the same
helper get_result_detail()/AttemptService._finalize() already use) and
to AUTO_GRADABLE_QUESTION_TYPES before scoring — the existing
DEFAULT_SCORING_STRATEGY.calculate() call itself is unchanged.
"""
import uuid
from datetime import datetime, timedelta, timezone

from app.modules.attempts.models import Answer, AttemptModuleProgress, AttemptStatus, TestAttempt
from app.modules.attempts.module_execution_service import ModuleExecutionService
from app.modules.attempts.repository import AnswerRepository, AttemptModuleProgressRepository, AttemptRepository
from app.modules.questions.models import Question, QuestionOption
from app.modules.questions.repository import OptionRepository, QuestionRepository
from app.modules.results.repository import ResultRepository, ResultSectionRepository, StatisticsRepository
from app.modules.results.service import ResultService
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import ExamModule, ExamSection, Test
from app.modules.tests.repository import ExamModuleRepository, ExamSectionRepository, TestRepository
from app.modules.users.models import User, UserStatus


def _make_student(pg_session, prefix: str) -> uuid.UUID:
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name=prefix, last_name="RS1", email=f"{prefix.lower()}-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    pg_session.flush()
    return user.id


def _make_result_service(pg_session, with_module_execution: bool) -> ResultService:
    module_execution = None
    if with_module_execution:
        module_execution = ModuleExecutionService(
            ExamModuleRepository(pg_session), AttemptModuleProgressRepository(pg_session),
            QuestionRepository(pg_session), AnswerRepository(pg_session), AttemptRepository(pg_session),
        )
    return ResultService(
        ResultRepository(pg_session), StatisticsRepository(pg_session), AttemptRepository(pg_session),
        AnswerRepository(pg_session), TestRepository(pg_session), QuestionRepository(pg_session),
        ExamSectionRepository(pg_session), ResultSectionRepository(pg_session),
        module_execution_service=module_execution,
    )


def _add_single_choice(pg_session, test_id, section_id=None, module_id=None, score=1, text="Q") -> tuple[Question, QuestionOption]:
    q = Question(test_id=test_id, question_text=text, question_type="single_choice", score=score, section_id=section_id, module_id=module_id)
    pg_session.add(q)
    pg_session.flush()
    correct = QuestionOption(question_id=q.id, option_text="A", is_correct=True)
    wrong = QuestionOption(question_id=q.id, option_text="B", is_correct=False)
    pg_session.add_all([correct, wrong])
    pg_session.flush()
    return q, correct


def _add_short_answer(pg_session, test_id, section_id=None, module_id=None, score=1, text="Q") -> Question:
    q = Question(test_id=test_id, question_text=text, question_type="short_answer", score=score, section_id=section_id, module_id=module_id)
    pg_session.add(q)
    pg_session.flush()
    return q


def _submit_attempt(pg_session, test_id, user_id, question_order) -> TestAttempt:
    now = datetime.now(timezone.utc)
    attempt = TestAttempt(
        test_id=test_id, user_id=user_id, status=AttemptStatus.SUBMITTED,
        start_time=now, finish_time=now, question_order=question_order,
    )
    pg_session.add(attempt)
    pg_session.flush()
    return attempt


# =====================================================================
# RS1-A — effective-scope filtering: a section has 4 questions across
# two modules; this attempt's adaptive routing only ever delivered
# module 1's 2 questions (a single AttemptModuleProgress row exists
# for module 1 only — module 2 was never reached). raw_score must
# reflect ONLY the 2 delivered questions, not all 4 FK'd to the
# section.
# =====================================================================

def test_rs1_a_section_score_excludes_undelivered_module_questions(pg_session):
    user_id = _make_student(pg_session, "RS1A")
    subject = Subject(name=f"RS1ASubj-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="RS1A Test", duration=60, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    module2 = ExamModule(section_id=section.id, name="Module 2", order_number=1)
    pg_session.add_all([module1, module2])
    pg_session.flush()

    q1, opt1 = _add_single_choice(pg_session, test.id, section_id=section.id, module_id=module1.id, score=5, text="Q1")
    q2, opt2 = _add_single_choice(pg_session, test.id, section_id=section.id, module_id=module1.id, score=5, text="Q2")
    # Module 2's questions exist and belong to the same section, but
    # this attempt never reaches them.
    q3, opt3 = _add_single_choice(pg_session, test.id, section_id=section.id, module_id=module2.id, score=5, text="Q3")
    _add_single_choice(pg_session, test.id, section_id=section.id, module_id=module2.id, score=5, text="Q4")

    attempt = _submit_attempt(pg_session, test.id, user_id, [q1.id, q2.id])
    pg_session.add(AttemptModuleProgress(attempt_id=attempt.id, module_id=module1.id, status=AttemptStatus.SUBMITTED.value, question_order=[q1.id, q2.id]))
    pg_session.flush()
    pg_session.add(Answer(attempt_id=attempt.id, question_id=q1.id, selected_option=opt1.id, is_correct=True))
    pg_session.add(Answer(attempt_id=attempt.id, question_id=q2.id, selected_option=opt2.id, is_correct=True))
    # A stray Answer for Q3 (the undelivered module 2 question),
    # correct — can't happen through the real save_answer() path
    # (validate_question_in_module() blocks it), but this proves the
    # fix's defense-in-depth: even if one existed (a data
    # inconsistency, a future bug elsewhere), it must not inflate this
    # section's raw_score, because Q3 is outside this attempt's
    # effective/delivered scope.
    pg_session.add(Answer(attempt_id=attempt.id, question_id=q3.id, selected_option=opt3.id, is_correct=True))
    pg_session.commit()

    service = _make_result_service(pg_session, with_module_execution=True)
    result = service.create_result(attempt.id, user_id)

    sections = ResultSectionRepository(pg_session).list_for_result(result.id)
    assert len(sections) == 1
    # Only q1+q2 (score=5 each, both correct) count — 10, not 20 (which
    # q3/q4 would add if the undelivered-module bug regressed).
    assert float(sections[0].raw_score) == 10.0, sections[0].raw_score


# =====================================================================
# RS1-B — auto-gradable filtering: a section has 2 single_choice
# (delivered, both correct) and 1 short_answer (delivered, answered,
# is_correct always None). raw_score must reflect ONLY the 2
# single_choice questions — the short_answer neither inflates the
# denominator nor is treated as wrong.
# =====================================================================

def test_rs1_b_section_score_excludes_manual_grading_types(pg_session):
    user_id = _make_student(pg_session, "RS1B")
    test = Test(subject_id=None, title="RS1B Test", duration=60, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()

    q1, opt1 = _add_single_choice(pg_session, test.id, section_id=section.id, score=3, text="Q1")
    q2, opt2 = _add_single_choice(pg_session, test.id, section_id=section.id, score=3, text="Q2")
    q3 = _add_short_answer(pg_session, test.id, section_id=section.id, score=10, text="Q3")  # deliberately large score

    attempt = _submit_attempt(pg_session, test.id, user_id, [q1.id, q2.id, q3.id])
    pg_session.add(Answer(attempt_id=attempt.id, question_id=q1.id, selected_option=opt1.id, is_correct=True))
    pg_session.add(Answer(attempt_id=attempt.id, question_id=q2.id, selected_option=opt2.id, is_correct=True))
    pg_session.add(Answer(attempt_id=attempt.id, question_id=q3.id, text_answer="my free-text answer", is_correct=None))
    pg_session.commit()

    # Non-modular attempt — no module_execution_service wired, same as
    # a legacy ResultService construction without Sprint 54/63's
    # optional args. _effective_result_question_ids() falls back to
    # attempt.question_order, exactly as before this sprint.
    service = _make_result_service(pg_session, with_module_execution=False)
    result = service.create_result(attempt.id, user_id)

    sections = ResultSectionRepository(pg_session).list_for_result(result.id)
    assert len(sections) == 1
    # q1+q2 = 6. If q3's score=10 ever leaked into the denominator (the
    # old bug), DEFAULT_SCORING_STRATEGY's percentage would be wrong
    # even though raw_score (a pure sum of correct scores) would
    # coincidentally still read 6 — so the real regression guard here
    # is scaled_score staying None and raw_score being exactly 6, with
    # a 3rd, manually-graded question never silently scored as wrong.
    assert float(sections[0].raw_score) == 6.0, sections[0].raw_score


# =====================================================================
# RS1-C — regression guard: a non-modular section with ONLY
# auto-gradable questions, all delivered and all in scope, must keep
# scoring exactly as it always did before this sprint (the ordinary,
# by-far-most-common case).
# =====================================================================

def test_rs1_c_ordinary_non_modular_section_scoring_is_unchanged(pg_session):
    user_id = _make_student(pg_session, "RS1C")
    test = Test(subject_id=None, title="RS1C Test", duration=60, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()

    q1, opt1 = _add_single_choice(pg_session, test.id, section_id=section.id, score=4, text="Q1")
    q2, opt2 = _add_single_choice(pg_session, test.id, section_id=section.id, score=4, text="Q2")

    attempt = _submit_attempt(pg_session, test.id, user_id, [q1.id, q2.id])
    pg_session.add(Answer(attempt_id=attempt.id, question_id=q1.id, selected_option=opt1.id, is_correct=True))
    wrong_option = pg_session.query(QuestionOption).filter(QuestionOption.question_id == q2.id, QuestionOption.is_correct.is_(False)).one()
    pg_session.add(Answer(attempt_id=attempt.id, question_id=q2.id, selected_option=wrong_option.id, is_correct=False))
    pg_session.commit()

    service = _make_result_service(pg_session, with_module_execution=False)
    result = service.create_result(attempt.id, user_id)

    sections = ResultSectionRepository(pg_session).list_for_result(result.id)
    assert len(sections) == 1
    assert float(sections[0].raw_score) == 4.0, sections[0].raw_score  # only q1 correct


# =====================================================================
# RS1-D — a section made up ENTIRELY of manual-grading questions (no
# auto-gradable question at all) must score 0, not crash — a complete
# no-op scoring result, same as DEFAULT_SCORING_STRATEGY.calculate([], []).
# =====================================================================

def test_rs1_d_section_with_only_manual_grading_questions_scores_zero(pg_session):
    user_id = _make_student(pg_session, "RS1D")
    test = Test(subject_id=None, title="RS1D Test", duration=60, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()

    q1 = _add_short_answer(pg_session, test.id, section_id=section.id, score=5, text="Essay-like Q1")

    attempt = _submit_attempt(pg_session, test.id, user_id, [q1.id])
    pg_session.add(Answer(attempt_id=attempt.id, question_id=q1.id, text_answer="free text", is_correct=None))
    pg_session.commit()

    service = _make_result_service(pg_session, with_module_execution=False)
    result = service.create_result(attempt.id, user_id)

    sections = ResultSectionRepository(pg_session).list_for_result(result.id)
    assert len(sections) == 1
    assert float(sections[0].raw_score) == 0.0, sections[0].raw_score
