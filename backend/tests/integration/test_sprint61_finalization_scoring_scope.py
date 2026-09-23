"""
Sprint 61 — S61-C. Finalization Scoring Scope integration tests, against
real PostgreSQL (Sprint 40's pg_session infrastructure).

Audit finding (Sprint 61 Architecture Audit, Section 6): AttemptService
._finalize()/_build_result() scored/reported against the whole-test
TestAttempt.question_order snapshot unconditionally, even for a modular
attempt. That snapshot is built once at start_attempt() from EVERY
question in the test regardless of module — so any question the student
was never actually delivered through a module (a module skipped by a
future adaptive-routing strategy, or a legacy/orphan question with
module_id = NULL) still counted 0 toward the numerator while its score
still inflated the denominator, silently deflating the final percentage.

Fix: AttemptService._effective_scoring_question_ids() now delegates to
ModuleExecutionService.get_effective_question_ids() for any attempt that
actually has AttemptModuleProgress rows — the deduplicated, order-
preserving union of every module's delivered question_order — falling
back to the original whole-test attempt.question_order for a non-modular
attempt (or the defensive no-progress-rows edge case), which is
byte-identical to pre-Sprint-61 behavior in both of those cases.

Also added: AttemptService.submit_attempt() now rejects a whole-attempt
submit on an incomplete modular exam via the existing
ModuleExecutionService.is_exam_complete() lifecycle check (new
ExamNotCompleteException, 409) — closing the gap where a student could
bypass the remaining routed modules by calling the whole-attempt submit
endpoint directly. is_exam_complete() already returns True vacuously for
a non-modular test (it has no ExamModule rows to be incomplete), so this
never affects any non-modular attempt.

The current, only-wired-in-production SequentialRoutingStrategy never
actually skips a module (it always advances strictly in order_number),
so a genuine "module skipped by adaptive routing" state cannot be
produced today through the real submit_module()/routing flow — Sprint 61
does not implement adaptive routing. Test 3 below therefore constructs
that state directly via AttemptModuleProgressRepository (exactly the
same "test-only synchronization/construction, not a code change"
approach earlier sprints used for concurrency proofs) and calls
AttemptService._finalize()/_build_result() directly to exercise the
scoring-scope fix in isolation from the (separately tested) whole-submit
guard.
"""
import uuid

import pytest

from app.modules.attempts.exceptions import ExamNotCompleteException
from app.modules.attempts.models import AttemptModuleProgress, AttemptStatus
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
    user = User(role_id=role.id, first_name="F61", last_name="X", email=f"f61-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
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
    """Creates a Test with n_modules ExamModules (one section), one
    single_choice question per module (score points each). Returns
    (test, [modules...], [(question, correct_option), ...] one per module)."""
    subject = Subject(name=f"S61-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Sprint61 Modular", duration=120, question_count=0, status="published")
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


# --- Test 1: non-modular regression (module_execution wired, no ExamModule rows) ---

def test_non_modular_scoring_and_submit_guard_unaffected(pg_session):
    student_id = _make_student(pg_session)
    subject = Subject(name=f"S61-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Non-modular", duration=30, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    q1, opt1 = _make_question(pg_session, test.id)
    q2, opt2 = _make_question(pg_session, test.id)
    pg_session.commit()

    service = _make_service(pg_session)  # module_execution IS wired, but this test has no ExamModule rows
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    progress_rows = pg_session.query(AttemptModuleProgress).filter(AttemptModuleProgress.attempt_id == attempt.id).all()
    assert progress_rows == []  # confirms this really is the non-modular path

    service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()
    # q2 left unanswered -> counts as wrong, exactly as before Sprint 61

    result = service.submit_attempt(attempt.id, student_id)  # must NOT raise ExamNotCompleteException
    pg_session.commit()

    assert result.status == "submitted"
    assert result.total_questions == 2
    assert result.correct_count == 1
    assert result.percentage == 50.0


# --- Test 2: modular, all modules completed -> same score as before ---

def test_modular_all_modules_completed_scores_correctly(pg_session):
    student_id = _make_student(pg_session)
    test, modules, module_questions = _make_modular_test(pg_session, n_modules=2, score=1)
    module1, module2 = modules
    q1, opt1 = module_questions[0]
    q2, opt2 = module_questions[1]

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()
    outcome1 = service.submit_module(attempt.id, module1.id, student_id)
    pg_session.commit()
    assert outcome1["completed"] is False
    assert outcome1["next_module_id"] == module2.id

    service.save_answer(attempt.id, student_id, q2.id, selected_option=opt2.id)
    pg_session.commit()
    outcome2 = service.submit_module(attempt.id, module2.id, student_id)
    pg_session.commit()

    assert outcome2["completed"] is True
    result = outcome2["result"]
    assert result.status == "submitted"
    assert result.total_questions == 2
    assert result.correct_count == 2
    assert result.percentage == 100.0


# --- Test 3: skipped module excluded from both numerator and denominator ---

def test_skipped_module_excluded_from_scoring(pg_session):
    """Module 2 is deliberately never given an AttemptModuleProgress row
    (simulating a future routing strategy skipping it entirely — the
    live SequentialRoutingStrategy cannot produce this today, so it is
    constructed directly; see module docstring). Module 2's question
    carries an outsized score so a wrongly-included denominator would be
    immediately visible in the asserted percentage."""
    student_id = _make_student(pg_session)
    test, modules, module_questions = _make_modular_test(pg_session, n_modules=3, score=1)
    module1, module2, module3 = modules
    q1, opt1 = module_questions[0]
    q2, _opt2 = module_questions[1]
    q3, opt3 = module_questions[2]

    q2.score = 5  # would obviously skew the percentage if wrongly counted
    pg_session.flush()
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)  # creates module1's progress row only
    pg_session.commit()

    # Answer q1 while module1 is still the active (in_progress) module —
    # module-scoped validation only allows answering the active module's
    # own questions, exactly as in normal execution.
    service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()

    progress_repo = AttemptModuleProgressRepository(pg_session)
    m1_progress = progress_repo.get_for_attempt_and_module(attempt.id, module1.id)
    assert m1_progress is not None
    progress_repo.update(m1_progress, {"status": AttemptStatus.SUBMITTED.value})

    # module2 never gets a progress row at all — the "skipped" module.
    m3_progress = AttemptModuleProgress(
        attempt_id=attempt.id, module_id=module3.id, status=AttemptStatus.IN_PROGRESS.value, question_order=[q3.id],
    )
    progress_repo.create(m3_progress)
    pg_session.commit()

    service.save_answer(attempt.id, student_id, q3.id, selected_option=opt3.id)
    pg_session.commit()

    service._finalize(attempt, AttemptStatus.SUBMITTED)
    pg_session.commit()
    result = service._build_result(attempt)

    assert result.total_questions == 2  # q1 + q3 only — module2's q2 excluded
    assert result.correct_count == 2
    assert result.percentage == 100.0  # would be ~28.57% (2/7) if q2's score=5 leaked into total_possible


# --- Test 4: module_id = NULL question excluded from modular scoring ---

def test_null_module_question_excluded_from_modular_scoring(pg_session):
    student_id = _make_student(pg_session)
    test, modules, module_questions = _make_modular_test(pg_session, n_modules=1, score=1)
    module1 = modules[0]
    q1, opt1 = module_questions[0]
    # Orphan question: module_id=None. list_by_module() only matches an
    # exact module_id, so this can never appear in ANY module's
    # question_order — yet it IS part of the legacy whole-test
    # attempt.question_order snapshot built at start_attempt().
    q_orphan, _opt_orphan = _make_question(pg_session, test.id, module_id=None, score=3)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()
    assert q_orphan.id in (attempt.question_order or [])  # confirms it's in the whole-test snapshot

    service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()
    outcome = service.submit_module(attempt.id, module1.id, student_id)
    pg_session.commit()

    assert outcome["completed"] is True
    result = outcome["result"]
    assert result.total_questions == 1  # only q1 — the orphan is excluded
    assert result.correct_count == 1
    assert result.percentage == 100.0  # would be 25% (1/4) if the orphan's score=3 leaked in


# --- Test 5: duplicate question IDs across module progress are not double-counted ---

def test_effective_question_ids_deduplicates_across_progress_rows(pg_session):
    """White-box test of the dedup guarantee (Sprint 61 audit edge case
    E). A Question has exactly one module_id, so the same question_id
    cannot naturally appear in two different modules' question_order —
    this constructs that state directly to verify
    get_effective_question_ids() would not double-count it if it ever
    did (e.g. a future data inconsistency or routing edge case)."""
    student_id = _make_student(pg_session)
    test, modules, module_questions = _make_modular_test(pg_session, n_modules=2, score=1)
    module2 = modules[1]
    q1, _opt1 = module_questions[0]

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    progress_repo = AttemptModuleProgressRepository(pg_session)
    dup_progress = AttemptModuleProgress(
        attempt_id=attempt.id, module_id=module2.id, status=AttemptStatus.IN_PROGRESS.value, question_order=[q1.id],
    )
    progress_repo.create(dup_progress)
    pg_session.commit()

    effective_ids = service.module_execution.get_effective_question_ids(attempt.id)

    assert effective_ids.count(q1.id) == 1
    assert len(effective_ids) == len(set(effective_ids))


# --- Test 6: incomplete modular exam rejects whole-attempt submit ---

def test_incomplete_modular_exam_rejects_whole_attempt_submit(pg_session):
    student_id = _make_student(pg_session)
    test, modules, module_questions = _make_modular_test(pg_session, n_modules=2, score=1)
    module1, _module2 = modules
    q1, opt1 = module_questions[0]

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)  # module1's progress only, still in_progress
    pg_session.commit()
    service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()

    with pytest.raises(ExamNotCompleteException):
        service.submit_attempt(attempt.id, student_id)

    reloaded = AttemptRepository(pg_session).get_by_id(attempt.id)
    assert reloaded.status == "in_progress"  # not finalized
    assert reloaded.score is None
    assert reloaded.percentage is None


# --- Test 7: completed modular lifecycle still finalizes correctly ---

def test_completed_modular_lifecycle_finalization_unaffected(pg_session):
    """Once every module is genuinely completed through submit_module()
    (the normal modular-exam lifecycle), the last module's own
    "completed" branch finalizes the attempt exactly as before Sprint 61
    (already covered numerically by Test 2 above). This test additionally
    confirms that a subsequent direct call to submit_attempt() on that
    now-finished attempt still raises the pre-existing
    AttemptNotActiveException (status already SUBMITTED) rather than the
    new ExamNotCompleteException — i.e. the new completeness guard sits
    behind, and never overrides, the original active-status check."""
    from app.modules.attempts.exceptions import AttemptNotActiveException

    student_id = _make_student(pg_session)
    test, modules, module_questions = _make_modular_test(pg_session, n_modules=1, score=1)
    module1 = modules[0]
    q1, opt1 = module_questions[0]

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()
    service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()

    outcome = service.submit_module(attempt.id, module1.id, student_id)
    pg_session.commit()
    assert outcome["completed"] is True
    assert outcome["result"].status == "submitted"
    assert outcome["result"].percentage == 100.0

    with pytest.raises(AttemptNotActiveException):
        service.submit_attempt(attempt.id, student_id)
