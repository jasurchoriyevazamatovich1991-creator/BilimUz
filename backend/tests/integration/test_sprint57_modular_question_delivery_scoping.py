"""
Sprint 57 — Modular Question Delivery Scoping, against real PostgreSQL
(Sprint 40's infrastructure — pg_session, TEST_DATABASE_URL). Matches
the established integration-test style for this subsystem (see
test_module_execution.py): AttemptService/ModuleExecutionService are
constructed directly with real repositories, not through FastAPI's DI
or mocks, so both the modular and legacy execution paths run against
real DB constraints.

Bug fixed: AttemptService.get_attempt_detail() used to return every
question in attempt.question_order (the whole test's question list,
built once at start_attempt) regardless of which module was active —
so a Student on Module 1 of a modular exam could already see every
future module's question content. save_answer() already correctly
scoped ANSWER SUBMISSION to the active module via
get_active_module_progress()/validate_question_in_module(); this
sprint makes QUESTION DELIVERY follow the same boundary.
"""
import uuid

import pytest

from app.modules.attempts.models import AttemptModuleProgress
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


def _make_question_with_correct_option(pg_session, test_id, module_id=None, text="Q") -> tuple[Question, QuestionOption]:
    q = Question(test_id=test_id, question_text=text, question_type="single_choice", score=1, module_id=module_id)
    pg_session.add(q)
    pg_session.flush()
    correct = QuestionOption(question_id=q.id, option_text="A", is_correct=True)
    wrong = QuestionOption(question_id=q.id, option_text="B", is_correct=False)
    pg_session.add_all([correct, wrong])
    pg_session.flush()
    return q, correct


def _make_modular_test_with_two_modules(pg_session):
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

    q1, opt1 = _make_question_with_correct_option(pg_session, test.id, module_id=module1.id, text="Q1")
    q2, opt2 = _make_question_with_correct_option(pg_session, test.id, module_id=module1.id, text="Q2")
    q3, opt3 = _make_question_with_correct_option(pg_session, test.id, module_id=module1.id, text="Q3")
    q4, opt4 = _make_question_with_correct_option(pg_session, test.id, module_id=module2.id, text="Q4")
    q5, opt5 = _make_question_with_correct_option(pg_session, test.id, module_id=module2.id, text="Q5")
    q6, opt6 = _make_question_with_correct_option(pg_session, test.id, module_id=module2.id, text="Q6")
    pg_session.commit()

    return test, module1, module2, (q1, q2, q3), (opt1, opt2, opt3), (q4, q5, q6), (opt4, opt5, opt6)


# --- TEST 1 & 2: Module 1 active — only Module 1 questions visible ---

def test_active_module_1_returns_only_its_own_questions(pg_session):
    student_id = _make_student(pg_session)
    test, module1, module2, m1_questions, m1_options, m2_questions, _ = _make_modular_test_with_two_modules(pg_session)

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)

    returned_ids = {q.id for q in detail.questions}
    m1_ids = {q.id for q in m1_questions}
    m2_ids = {q.id for q in m2_questions}

    # TEST 1: only Module 1 questions returned.
    assert returned_ids == m1_ids
    # TEST 2: Module 2 (future module) questions are absent.
    assert returned_ids.isdisjoint(m2_ids)


# --- TEST 3: after Module 1 submit, only Module 2 questions visible ---

def test_after_module_1_submit_only_module_2_questions_returned(pg_session):
    student_id = _make_student(pg_session)
    test, module1, module2, m1_questions, m1_options, m2_questions, _ = _make_modular_test_with_two_modules(pg_session)

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    for q, opt in zip(m1_questions, m1_options):
        service.save_answer(attempt.id, student_id, q.id, selected_option=opt.id)
    pg_session.commit()

    outcome = service.submit_module(attempt.id, module1.id, student_id)
    pg_session.commit()
    assert outcome["completed"] is False
    assert outcome["next_module_id"] == module2.id

    detail = service.get_attempt_detail(attempt.id, student_id)
    returned_ids = {q.id for q in detail.questions}
    m1_ids = {q.id for q in m1_questions}
    m2_ids = {q.id for q in m2_questions}

    assert returned_ids == m2_ids
    assert returned_ids.isdisjoint(m1_ids)


# --- TEST 4: non-modular attempt — existing behavior unchanged ---

def test_non_modular_attempt_returns_all_questions_unchanged(pg_session):
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Plain Test", duration=30, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    q1, _opt1 = _make_question_with_correct_option(pg_session, test.id, text="Q1")
    q2, _opt2 = _make_question_with_correct_option(pg_session, test.id, text="Q2")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    # No AttemptModuleProgress exists for a moduleless test — confirms
    # this is the true non-modular path, not just an empty module.
    assert pg_session.query(AttemptModuleProgress).filter(AttemptModuleProgress.attempt_id == attempt.id).count() == 0

    detail = service.get_attempt_detail(attempt.id, student_id)

    assert {q.id for q in detail.questions} == {q1.id, q2.id}
    assert set(attempt.question_order) == {q1.id, q2.id}


# --- TEST 5: answered-state is also scoped to the active module ---

def test_answered_state_is_scoped_to_active_module(pg_session):
    student_id = _make_student(pg_session)
    test, module1, module2, m1_questions, m1_options, m2_questions, _ = _make_modular_test_with_two_modules(pg_session)

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    # Answer only the first Module 1 question.
    service.save_answer(attempt.id, student_id, m1_questions[0].id, selected_option=m1_options[0].id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)

    answered_ids = {a.question_id for a in detail.answered}
    m1_ids = {q.id for q in m1_questions}
    m2_ids = {q.id for q in m2_questions}

    # Answered-state list contains exactly Module 1's questions (the
    # active module) — not the whole test, and not Module 2.
    assert answered_ids == m1_ids
    assert answered_ids.isdisjoint(m2_ids)

    first_state = next(a for a in detail.answered if a.question_id == m1_questions[0].id)
    assert first_state.is_answered is True
    assert first_state.selected_option == m1_options[0].id

    second_state = next(a for a in detail.answered if a.question_id == m1_questions[1].id)
    assert second_state.is_answered is False


# --- Edge case: module execution configured, no active progress row ---

def test_no_active_module_progress_falls_back_to_whole_attempt_question_order(pg_session):
    """Mirrors the exact tolerance save_answer() already has (service.py
    line ~159: 'if active_progress is not None') for the same edge
    case — module execution is wired, but no AttemptModuleProgress row
    is currently 'in_progress' for this attempt (e.g. a data/edge state
    outside the normal flow). Delivery must not crash or return nothing;
    it falls back to attempt.question_order, exactly like before this
    fix."""
    student_id = _make_student(pg_session)
    test, module1, module2, m1_questions, m1_options, m2_questions, _ = _make_modular_test_with_two_modules(pg_session)

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    # Force the "no active progress" edge case by marking Module 1's
    # row as no longer in_progress without creating Module 2's (i.e.
    # without going through the normal submit_module() flow).
    progress = pg_session.query(AttemptModuleProgress).filter(
        AttemptModuleProgress.attempt_id == attempt.id, AttemptModuleProgress.module_id == module1.id,
    ).one()
    progress.status = "submitted"
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)

    returned_ids = {q.id for q in detail.questions}
    all_ids = {q.id for q in m1_questions} | {q.id for q in m2_questions}
    assert returned_ids == all_ids
