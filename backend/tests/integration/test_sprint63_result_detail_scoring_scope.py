"""
Sprint 63 — S63-A. Result Detail Scoring Scope Fix integration tests,
against real PostgreSQL (Sprint 40's pg_session infrastructure), mirroring
Sprint 61's own test style/construction helpers.

Audit finding (Sprint 63 Architecture Audit, Section 5): Sprint 61 fixed
AttemptService._finalize()/_build_result() to use the deduplicated,
module-scoped "effective question ids" (ModuleExecutionService.
get_effective_question_ids()) instead of the raw whole-test
attempt.question_order snapshot. But ResultService.get_result_detail() —
a separate, student-reachable endpoint (GET /results/{id}) — kept using
the raw attempt.question_order directly, so a modular attempt where a
student was routed through only some modules could report a DIFFERENT
total_questions/unanswered count on GET /results/{id} than on
GET /attempts/{id}/result (which already used the fixed scope).

Fix: ResultService._effective_result_question_ids() now delegates to the
exact same ModuleExecutionService.get_effective_question_ids() helper
Sprint 61 already built and AttemptService already uses — no second
implementation of the algorithm — falling back to attempt.question_order
when there are no module progress rows at all (non-modular attempts, or
a legacy ResultService construction with no module_execution_service
wired), which is byte-identical to pre-Sprint-63 behavior in that case.

This sprint does NOT touch Result.score/Result.percentage (already
correct since they're copied from the already-fixed attempt fields at
create_result() time) — only get_result_detail()'s question-scope-derived
fields (total_questions, correct/incorrect/unanswered counts, the
question review list) are affected.
"""
import uuid

import pytest

from app.modules.attempts.models import AttemptModuleProgress, AttemptStatus
from app.modules.attempts.module_execution_service import ModuleExecutionService
from app.modules.attempts.repository import AnswerRepository, AttemptModuleProgressRepository, AttemptRepository
from app.modules.attempts.service import AttemptService
from app.modules.questions.models import Question, QuestionOption
from app.modules.questions.repository import OptionRepository, QuestionRepository
from app.modules.results.exceptions import ResultNotFoundException
from app.modules.results.repository import ResultRepository, StatisticsRepository
from app.modules.results.service import ResultService
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import ExamModule, ExamSection, Test
from app.modules.tests.repository import ExamModuleRepository, TestRepository
from app.modules.users.models import User, UserStatus


def _make_student(pg_session, label="F63") -> uuid.UUID:
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name=label, last_name="X", email=f"{label.lower()}-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    pg_session.flush()
    return user.id


def _module_execution_service(pg_session) -> ModuleExecutionService:
    return ModuleExecutionService(
        ExamModuleRepository(pg_session), AttemptModuleProgressRepository(pg_session),
        QuestionRepository(pg_session), AnswerRepository(pg_session), AttemptRepository(pg_session),
    )


def _attempt_service(pg_session, module_execution: ModuleExecutionService | None = None) -> AttemptService:
    """Production-realistic construction — module_execution/module_repo
    always wired, matching get_attempt_service()'s real FastAPI DI (same
    pattern as Sprint 61's own _make_service helper)."""
    module_execution = module_execution or _module_execution_service(pg_session)
    return AttemptService(
        AttemptRepository(pg_session), AnswerRepository(pg_session), TestRepository(pg_session),
        QuestionRepository(pg_session), OptionRepository(pg_session),
        module_execution, ExamModuleRepository(pg_session),
    )


def _result_service(pg_session, module_execution: ModuleExecutionService | None = None) -> ResultService:
    """Production-realistic construction — module_execution_service wired,
    matching Sprint 63's real get_result_service() FastAPI DI. Tests that
    want to exercise the pre-Sprint-63 fallback pass module_execution=None
    explicitly (a legacy construction)."""
    return ResultService(
        ResultRepository(pg_session), StatisticsRepository(pg_session), AttemptRepository(pg_session),
        AnswerRepository(pg_session), TestRepository(pg_session), QuestionRepository(pg_session),
        module_execution_service=module_execution,
    )


def _make_question(pg_session, test_id, module_id=None, score=1) -> tuple[Question, QuestionOption]:
    q = Question(test_id=test_id, question_text="Q", question_type="single_choice", score=score, module_id=module_id)
    pg_session.add(q)
    pg_session.flush()
    correct = QuestionOption(question_id=q.id, option_text="A", is_correct=True)
    wrong = QuestionOption(question_id=q.id, option_text="B", is_correct=False)
    pg_session.add_all([correct, wrong])
    pg_session.flush()
    return q, correct


def _make_modular_test(pg_session, n_modules: int, score: int = 1):
    """Same helper shape as Sprint 61's own _make_modular_test."""
    subject = Subject(name=f"S63-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Sprint63 Modular", duration=120, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    modules = []
    for i in range(n_modules):
        m = ExamModule(section_id=section.id, name=f"Module {i + 1}", order_number=i)
        pg_session.add(m)
        modules.append(m)
    pg_session.flush()
    module_questions = [_make_question(pg_session, test.id, module_id=m.id, score=score) for m in modules]
    pg_session.commit()
    return test, modules, module_questions


# --- Test 1: non-modular result detail regression (unchanged) ---

def test_non_modular_result_detail_unaffected(pg_session):
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S63-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Non-modular", duration=30, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    q1, opt1 = _make_question(pg_session, test.id)
    q2, opt2 = _make_question(pg_session, test.id)
    pg_session.commit()

    module_execution = _module_execution_service(pg_session)
    attempt_service = _attempt_service(pg_session, module_execution)
    result_service = _result_service(pg_session, module_execution)  # module_execution_service wired, same as production

    attempt = attempt_service.start_attempt(test.id, student_id)
    pg_session.commit()
    progress_rows = pg_session.query(AttemptModuleProgress).filter(AttemptModuleProgress.attempt_id == attempt.id).all()
    assert progress_rows == []  # confirms this really is the non-modular path

    attempt_service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()
    # q2 left unanswered

    attempt_service.submit_attempt(attempt.id, student_id)
    pg_session.commit()
    result = result_service.create_result(attempt.id, student_id)
    pg_session.commit()

    detail = result_service.get_result_detail(result.id, student_id)
    assert detail.total_questions == 2
    assert detail.correct_answers == 1
    assert detail.unanswered == 1
    assert float(detail.percentage) == 50.0


# --- Test 2: modular, all modules completed -> total_questions matches effective delivered count ---

def test_modular_all_modules_completed_result_detail(pg_session):
    student_id = _make_student(pg_session)
    test, modules, module_questions = _make_modular_test(pg_session, n_modules=2, score=1)
    module1, module2 = modules
    q1, opt1 = module_questions[0]
    q2, opt2 = module_questions[1]

    module_execution = _module_execution_service(pg_session)
    attempt_service = _attempt_service(pg_session, module_execution)
    result_service = _result_service(pg_session, module_execution)

    attempt = attempt_service.start_attempt(test.id, student_id)
    pg_session.commit()

    attempt_service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()
    attempt_service.submit_module(attempt.id, module1.id, student_id)
    pg_session.commit()

    attempt_service.save_answer(attempt.id, student_id, q2.id, selected_option=opt2.id)
    pg_session.commit()
    outcome = attempt_service.submit_module(attempt.id, module2.id, student_id)
    pg_session.commit()
    assert outcome["completed"] is True

    result = result_service.create_result(attempt.id, student_id)
    pg_session.commit()

    detail = result_service.get_result_detail(result.id, student_id)
    assert detail.total_questions == 2  # effective delivered count, not the (in this case identical) test total
    assert detail.correct_answers == 2
    assert detail.unanswered == 0
    assert float(detail.percentage) == 100.0
    assert {qr.question_id for qr in detail.questions} == {q1.id, q2.id}


# --- Test 3: skipped module excluded from result detail ---

def test_skipped_module_excluded_from_result_detail(pg_session):
    """Module 2 is deliberately never given an AttemptModuleProgress row
    (the live SequentialRoutingStrategy cannot produce this today, so it
    is constructed directly — identical approach to Sprint 61's own Test
    3, isolating the result-detail fix from adaptive routing, which is
    out of this sprint's scope)."""
    student_id = _make_student(pg_session)
    test, modules, module_questions = _make_modular_test(pg_session, n_modules=3, score=1)
    module1, module2, module3 = modules
    q1, opt1 = module_questions[0]
    q2, _opt2 = module_questions[1]
    q3, opt3 = module_questions[2]

    q2.score = 5  # would obviously skew total_questions/percentage if wrongly included
    pg_session.flush()
    pg_session.commit()

    module_execution = _module_execution_service(pg_session)
    attempt_service = _attempt_service(pg_session, module_execution)
    result_service = _result_service(pg_session, module_execution)

    attempt = attempt_service.start_attempt(test.id, student_id)  # creates module1's progress row only
    pg_session.commit()

    attempt_service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()

    progress_repo = AttemptModuleProgressRepository(pg_session)
    m1_progress = progress_repo.get_for_attempt_and_module(attempt.id, module1.id)
    progress_repo.update(m1_progress, {"status": AttemptStatus.SUBMITTED.value})

    # module2 never gets a progress row at all — the "skipped" module.
    m3_progress = AttemptModuleProgress(
        attempt_id=attempt.id, module_id=module3.id, status=AttemptStatus.IN_PROGRESS.value, question_order=[q3.id],
    )
    progress_repo.create(m3_progress)
    pg_session.commit()

    attempt_service.save_answer(attempt.id, student_id, q3.id, selected_option=opt3.id)
    pg_session.commit()

    attempt_service._finalize(attempt, AttemptStatus.SUBMITTED)
    pg_session.commit()

    result = result_service.create_result(attempt.id, student_id)
    pg_session.commit()

    detail = result_service.get_result_detail(result.id, student_id)
    assert detail.total_questions == 2  # q1 + q3 only — module2's q2 excluded
    assert detail.correct_answers == 2
    assert detail.unanswered == 0
    assert {qr.question_id for qr in detail.questions} == {q1.id, q3.id}
    assert q2.id not in {qr.question_id for qr in detail.questions}


# --- Test 4: module_id=NULL (orphan) question excluded from modular result detail ---

def test_null_module_question_excluded_from_result_detail(pg_session):
    student_id = _make_student(pg_session)
    test, modules, module_questions = _make_modular_test(pg_session, n_modules=1, score=1)
    module1 = modules[0]
    q1, opt1 = module_questions[0]
    # Orphan question: module_id=None — part of the legacy whole-test
    # attempt.question_order snapshot, but never in any module's
    # question_order.
    q_orphan, _opt_orphan = _make_question(pg_session, test.id, module_id=None, score=3)
    pg_session.commit()

    module_execution = _module_execution_service(pg_session)
    attempt_service = _attempt_service(pg_session, module_execution)
    result_service = _result_service(pg_session, module_execution)

    attempt = attempt_service.start_attempt(test.id, student_id)
    pg_session.commit()
    assert q_orphan.id in (attempt.question_order or [])  # confirms it's in the whole-test snapshot

    attempt_service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()
    outcome = attempt_service.submit_module(attempt.id, module1.id, student_id)
    pg_session.commit()
    assert outcome["completed"] is True

    result = result_service.create_result(attempt.id, student_id)
    pg_session.commit()

    detail = result_service.get_result_detail(result.id, student_id)
    assert detail.total_questions == 1  # only q1 — the orphan is excluded
    assert q_orphan.id not in {qr.question_id for qr in detail.questions}


# --- Test 5: duplicate question IDs across module progress remain deduplicated in result detail ---

def test_duplicate_question_ids_deduplicated_in_result_detail(pg_session):
    student_id = _make_student(pg_session)
    test, modules, module_questions = _make_modular_test(pg_session, n_modules=2, score=1)
    module1, module2 = modules
    q1, opt1 = module_questions[0]

    module_execution = _module_execution_service(pg_session)
    attempt_service = _attempt_service(pg_session, module_execution)
    result_service = _result_service(pg_session, module_execution)

    attempt = attempt_service.start_attempt(test.id, student_id)
    pg_session.commit()

    # Force q1 to also appear in module2's progress row (a data
    # inconsistency that cannot happen naturally — one module_id per
    # Question — constructed directly to verify the dedup guarantee,
    # identical in spirit to Sprint 61's own Test 5).
    progress_repo = AttemptModuleProgressRepository(pg_session)
    dup_progress = AttemptModuleProgress(
        attempt_id=attempt.id, module_id=module2.id, status=AttemptStatus.IN_PROGRESS.value, question_order=[q1.id],
    )
    progress_repo.create(dup_progress)
    pg_session.commit()

    attempt_service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()

    attempt_service._finalize(attempt, AttemptStatus.SUBMITTED)
    pg_session.commit()

    result = result_service.create_result(attempt.id, student_id)
    pg_session.commit()

    detail = result_service.get_result_detail(result.id, student_id)
    question_ids_seen = [qr.question_id for qr in detail.questions]
    assert question_ids_seen.count(q1.id) == 1  # not double-counted
    assert detail.total_questions == len(set(question_ids_seen))


# --- Test 6: endpoint consistency between GET /attempts/{id}/result and GET /results/{id} ---

def test_attempt_result_and_result_detail_agree_on_question_scope(pg_session):
    """The exact regression this sprint fixes: for the same completed
    modular attempt, AttemptService._build_result() (GET /attempts/{id}
    /result) and ResultService.get_result_detail() (GET /results/{id})
    must now report the SAME total_questions."""
    student_id = _make_student(pg_session)
    test, modules, module_questions = _make_modular_test(pg_session, n_modules=3, score=1)
    module1, module2, module3 = modules
    q1, opt1 = module_questions[0]
    q2, _opt2 = module_questions[1]
    q3, opt3 = module_questions[2]

    module_execution = _module_execution_service(pg_session)
    attempt_service = _attempt_service(pg_session, module_execution)
    result_service = _result_service(pg_session, module_execution)

    attempt = attempt_service.start_attempt(test.id, student_id)
    pg_session.commit()
    attempt_service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()

    progress_repo = AttemptModuleProgressRepository(pg_session)
    m1_progress = progress_repo.get_for_attempt_and_module(attempt.id, module1.id)
    progress_repo.update(m1_progress, {"status": AttemptStatus.SUBMITTED.value})
    # module2 skipped entirely — same construction as Test 3.
    m3_progress = AttemptModuleProgress(
        attempt_id=attempt.id, module_id=module3.id, status=AttemptStatus.IN_PROGRESS.value, question_order=[q3.id],
    )
    progress_repo.create(m3_progress)
    pg_session.commit()
    attempt_service.save_answer(attempt.id, student_id, q3.id, selected_option=opt3.id)
    pg_session.commit()

    attempt_service._finalize(attempt, AttemptStatus.SUBMITTED)
    pg_session.commit()
    attempt_result = attempt_service._build_result(attempt)

    result = result_service.create_result(attempt.id, student_id)
    pg_session.commit()
    detail = result_service.get_result_detail(result.id, student_id)

    assert attempt_result.total_questions == detail.total_questions == 2  # q1 + q3, module2 excluded from both
    assert q2.id not in {qr.question_id for qr in detail.questions}


# --- Test 7: result ownership / IDOR regression ---

def test_result_detail_ownership_rejects_other_user(pg_session):
    student_id = _make_student(pg_session, "F63Owner")
    other_user_id = _make_student(pg_session, "F63Intruder")
    subject = Subject(name=f"S63-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="IDOR", duration=30, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    q1, opt1 = _make_question(pg_session, test.id)
    pg_session.commit()

    module_execution = _module_execution_service(pg_session)
    attempt_service = _attempt_service(pg_session, module_execution)
    result_service = _result_service(pg_session, module_execution)

    attempt = attempt_service.start_attempt(test.id, student_id)
    pg_session.commit()
    attempt_service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()
    attempt_service.submit_attempt(attempt.id, student_id)
    pg_session.commit()
    result = result_service.create_result(attempt.id, student_id)
    pg_session.commit()

    # The owner can read it.
    detail = result_service.get_result_detail(result.id, student_id)
    assert detail.id == result.id

    # A different user must NOT be able to retrieve it.
    with pytest.raises(ResultNotFoundException):
        result_service.get_result_detail(result.id, other_user_id)


# --- Test 8: Result.score / Result.percentage preserved unchanged by this sprint ---

def test_result_score_and_percentage_unchanged_by_scope_fix(pg_session):
    """This sprint only changes get_result_detail()'s question-scope-
    derived fields (total_questions/correct/incorrect/unanswered/review
    list) — Result.score/percentage themselves are untouched, still
    copied verbatim from the already-Sprint-61-fixed attempt fields at
    create_result() time."""
    student_id = _make_student(pg_session)
    test, modules, module_questions = _make_modular_test(pg_session, n_modules=3, score=1)
    module1, module2, module3 = modules
    q1, opt1 = module_questions[0]
    q2, _opt2 = module_questions[1]
    q3, opt3 = module_questions[2]

    module_execution = _module_execution_service(pg_session)
    attempt_service = _attempt_service(pg_session, module_execution)
    result_service = _result_service(pg_session, module_execution)

    attempt = attempt_service.start_attempt(test.id, student_id)
    pg_session.commit()
    attempt_service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()

    progress_repo = AttemptModuleProgressRepository(pg_session)
    m1_progress = progress_repo.get_for_attempt_and_module(attempt.id, module1.id)
    progress_repo.update(m1_progress, {"status": AttemptStatus.SUBMITTED.value})
    m3_progress = AttemptModuleProgress(
        attempt_id=attempt.id, module_id=module3.id, status=AttemptStatus.IN_PROGRESS.value, question_order=[q3.id],
    )
    progress_repo.create(m3_progress)
    pg_session.commit()
    attempt_service.save_answer(attempt.id, student_id, q3.id, selected_option=opt3.id)
    pg_session.commit()

    attempt_service._finalize(attempt, AttemptStatus.SUBMITTED)
    pg_session.commit()
    attempt_result = attempt_service._build_result(attempt)
    assert float(attempt_result.percentage) == 100.0  # would be ~28.57% if module2's q2 leaked into scope

    result = result_service.create_result(attempt.id, student_id)
    pg_session.commit()

    detail = result_service.get_result_detail(result.id, student_id)
    assert float(detail.percentage) == 100.0
    assert float(detail.score) == float(result.score) == float(attempt.score)
    assert float(detail.percentage) == float(result.percentage) == float(attempt.percentage)
