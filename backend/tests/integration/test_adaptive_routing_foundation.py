"""
Sprint 48 — Generic Adaptive Routing Foundation integration tests,
against real PostgreSQL (Sprint 40's infrastructure — pg_session,
TEST_DATABASE_URL).

No real adaptive algorithm, no GRE/SAT-specific routing, no public
endpoints — pure data foundation + a deterministic default strategy,
verified against real FK/nullable/SET NULL behavior mocks cannot check,
plus the pure-Python AdaptiveRoutingStrategy/ModuleAccessGuard shape.
"""
import uuid
from datetime import datetime, timedelta, timezone

from app.modules.attempts.adaptive_routing import (
    ModuleAccessDeniedException,
    ModuleAccessGuard,
    ModuleCandidate,
    ModulePerformance,
    SequentialRoutingStrategy,
)
from app.modules.attempts.models import AttemptModuleProgress, AttemptStatus, TestAttempt
from app.modules.attempts.repository import AttemptRepository
from app.modules.questions.models import Question
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import ExamModule, ExamSection, QuestionGroup, Test
from app.modules.users.models import User, UserStatus


def _make_student(pg_session) -> uuid.UUID:
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name="A", last_name="R", email=f"ar-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    pg_session.flush()
    return user.id


def _make_test_with_section(pg_session):
    subject = Subject(name=f"Subject-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Adaptive-like Test", duration=60, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Verbal", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    return test, section


# --- A/B/C/D: QuestionGroup.module_id ---

def test_question_group_can_be_associated_with_exam_module(pg_session):
    test, section = _make_test_with_section(pg_session)
    module = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    pg_session.add(module)
    pg_session.flush()
    group = QuestionGroup(test_id=test.id, title="Passage", order_number=0, module_id=module.id)
    pg_session.add(group)
    pg_session.flush()

    reloaded = pg_session.query(QuestionGroup).filter(QuestionGroup.id == group.id).one()
    assert reloaded.module_id == module.id


def test_question_group_module_id_nullable(pg_session):
    test, _section = _make_test_with_section(pg_session)
    group = QuestionGroup(test_id=test.id, title="No module group", order_number=0)
    pg_session.add(group)
    pg_session.flush()

    reloaded = pg_session.query(QuestionGroup).filter(QuestionGroup.id == group.id).one()
    assert reloaded.module_id is None


def test_deleting_module_sets_question_group_module_id_to_null(pg_session):
    test, section = _make_test_with_section(pg_session)
    module = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    pg_session.add(module)
    pg_session.flush()
    group = QuestionGroup(test_id=test.id, title="Passage", order_number=0, module_id=module.id)
    pg_session.add(group)
    pg_session.flush()

    pg_session.delete(module)
    pg_session.commit()

    reloaded = pg_session.query(QuestionGroup).filter(QuestionGroup.id == group.id).one()
    assert reloaded.module_id is None
    assert reloaded.test_id == test.id  # the group itself is NOT deleted


def test_existing_question_group_without_module_remains_valid(pg_session):
    test, _section = _make_test_with_section(pg_session)
    group = QuestionGroup(test_id=test.id, title="Plain group", order_number=0)
    pg_session.add(group)
    pg_session.commit()

    reloaded = pg_session.query(QuestionGroup).filter(QuestionGroup.id == group.id).one()
    assert reloaded.module_id is None
    assert reloaded.title == "Plain group"


# --- E/F: ExamModule routing metadata ---

def test_exam_module_routing_metadata_can_be_stored(pg_session):
    test, section = _make_test_with_section(pg_session)
    module = ExamModule(section_id=section.id, name="Module 2 - Harder", order_number=1, routing_group="verbal", routing_variant="harder")
    pg_session.add(module)
    pg_session.commit()

    reloaded = pg_session.query(ExamModule).filter(ExamModule.id == module.id).one()
    assert reloaded.routing_group == "verbal"
    assert reloaded.routing_variant == "harder"


def test_exam_module_routing_metadata_is_optional(pg_session):
    test, section = _make_test_with_section(pg_session)
    module = ExamModule(section_id=section.id, name="Plain Module", order_number=0)
    pg_session.add(module)
    pg_session.commit()

    reloaded = pg_session.query(ExamModule).filter(ExamModule.id == module.id).one()
    assert reloaded.routing_group is None
    assert reloaded.routing_variant is None


# --- G: no hardcoded GRE/SAT values anywhere in this test file's assertions (self-check) ---

def test_no_hardcoded_exam_specific_values_required(pg_session):
    """Confirms routing_group/routing_variant accept ANY string — the
    model itself has no enum/CHECK constraint tying it to a specific
    exam's terminology."""
    test, section = _make_test_with_section(pg_session)
    module = ExamModule(section_id=section.id, name="M", order_number=0, routing_group="arbitrary-label-123", routing_variant="anything")
    pg_session.add(module)
    pg_session.commit()
    reloaded = pg_session.query(ExamModule).filter(ExamModule.id == module.id).one()
    assert reloaded.routing_group == "arbitrary-label-123"


# --- H: AdaptiveRoutingStrategy interface ---

def test_sequential_routing_strategy_picks_next_module():
    strategy: object = SequentialRoutingStrategy()  # satisfies the AdaptiveRoutingStrategy Protocol
    m1_id, m2_id = uuid.uuid4(), uuid.uuid4()
    candidates = [
        ModuleCandidate(module_id=m1_id, order_number=0, routing_group=None, routing_variant=None),
        ModuleCandidate(module_id=m2_id, order_number=1, routing_group=None, routing_variant=None),
    ]

    class _FakeCompletedModule:
        order_number = 0

    decision = strategy.decide_next_module(_FakeCompletedModule(), ModulePerformance(correct_count=5, total_count=10), candidates)
    assert decision.next_module_id == m2_id


def test_sequential_routing_strategy_returns_none_at_end():
    strategy = SequentialRoutingStrategy()

    class _FakeCompletedModule:
        order_number = 1

    decision = strategy.decide_next_module(_FakeCompletedModule(), ModulePerformance(correct_count=5, total_count=10), [])
    assert decision.next_module_id is None


# --- I/K: AttemptModuleProgress preserves module assignment, non-adaptive attempts unchanged ---

def test_attempt_module_progress_preserves_module_assignment(pg_session):
    student_id = _make_student(pg_session)
    test, section = _make_test_with_section(pg_session)
    module = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    pg_session.add(module)
    pg_session.flush()
    attempt = TestAttempt(user_id=student_id, test_id=test.id, status=AttemptStatus.IN_PROGRESS, start_time=datetime.now(timezone.utc))
    pg_session.add(attempt)
    pg_session.flush()
    progress = AttemptModuleProgress(attempt_id=attempt.id, module_id=module.id, status=AttemptStatus.IN_PROGRESS)
    pg_session.add(progress)
    pg_session.commit()

    reloaded = pg_session.query(AttemptModuleProgress).filter(AttemptModuleProgress.id == progress.id).one()
    assert reloaded.attempt_id == attempt.id
    assert reloaded.module_id == module.id  # module_id alone IS the assignment identity — no separate table needed


def test_existing_non_adaptive_attempt_behavior_unchanged(pg_session):
    """A moduleless attempt (every existing Physics/generic test attempt)
    has zero AttemptModuleProgress rows — completely unaffected by this
    sprint's additions."""
    student_id = _make_student(pg_session)
    subject = Subject(name=f"Subject-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Plain Test", duration=30, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    attempt = TestAttempt(user_id=student_id, test_id=test.id, status=AttemptStatus.IN_PROGRESS, start_time=datetime.now(timezone.utc))
    pg_session.add(attempt)
    pg_session.commit()

    progress_rows = pg_session.query(AttemptModuleProgress).filter(AttemptModuleProgress.attempt_id == attempt.id).all()
    assert progress_rows == []


# --- J: question_order snapshot remains unchanged after source question changes ---

def test_question_order_snapshot_unaffected_by_later_question_changes(pg_session):
    student_id = _make_student(pg_session)
    test, section = _make_test_with_section(pg_session)
    module = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    pg_session.add(module)
    pg_session.flush()
    q1 = Question(test_id=test.id, question_text="Q1", question_type="single_choice", score=1, module_id=module.id)
    pg_session.add(q1)
    pg_session.flush()

    attempt = TestAttempt(user_id=student_id, test_id=test.id, status=AttemptStatus.IN_PROGRESS, start_time=datetime.now(timezone.utc))
    pg_session.add(attempt)
    pg_session.flush()
    progress = AttemptModuleProgress(attempt_id=attempt.id, module_id=module.id, status=AttemptStatus.IN_PROGRESS, question_order=[q1.id])
    pg_session.add(progress)
    pg_session.commit()

    q2 = Question(test_id=test.id, question_text="Q2 added later", question_type="single_choice", score=1, module_id=module.id)
    pg_session.add(q2)
    pg_session.commit()

    reloaded = pg_session.query(AttemptModuleProgress).filter(AttemptModuleProgress.id == progress.id).one()
    assert reloaded.question_order == [q1.id]
    assert q2.id not in reloaded.question_order


# --- L: Module timing remains server-side (ModuleAccessGuard) ---

def test_module_access_guard_denies_non_owner(pg_session):
    student_id = _make_student(pg_session)
    other_user_id = _make_student(pg_session)
    test, section = _make_test_with_section(pg_session)
    module = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    pg_session.add(module)
    pg_session.flush()
    attempt = TestAttempt(user_id=student_id, test_id=test.id, status=AttemptStatus.IN_PROGRESS, start_time=datetime.now(timezone.utc))
    pg_session.add(attempt)
    pg_session.flush()
    progress = AttemptModuleProgress(attempt_id=attempt.id, module_id=module.id, status=AttemptStatus.IN_PROGRESS)
    pg_session.add(progress)
    pg_session.commit()

    guard = ModuleAccessGuard(AttemptRepository(pg_session))
    try:
        guard.check_access(progress, attempt, other_user_id)
        assert False, "expected ModuleAccessDeniedException for non-owner"
    except ModuleAccessDeniedException:
        pass


def test_module_access_guard_allows_owner_with_valid_module(pg_session):
    student_id = _make_student(pg_session)
    test, section = _make_test_with_section(pg_session)
    module = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    pg_session.add(module)
    pg_session.flush()
    attempt = TestAttempt(user_id=student_id, test_id=test.id, status=AttemptStatus.IN_PROGRESS, start_time=datetime.now(timezone.utc))
    pg_session.add(attempt)
    pg_session.flush()
    progress = AttemptModuleProgress(attempt_id=attempt.id, module_id=module.id, status=AttemptStatus.IN_PROGRESS, expires_at=datetime.now(timezone.utc) + timedelta(minutes=30))
    pg_session.add(progress)
    pg_session.commit()

    guard = ModuleAccessGuard(AttemptRepository(pg_session))
    guard.check_access(progress, attempt, student_id)  # must not raise


def test_module_access_guard_denies_expired_module(pg_session):
    student_id = _make_student(pg_session)
    test, section = _make_test_with_section(pg_session)
    module = ExamModule(section_id=section.id, name="Module 1", order_number=0)
    pg_session.add(module)
    pg_session.flush()
    attempt = TestAttempt(user_id=student_id, test_id=test.id, status=AttemptStatus.IN_PROGRESS, start_time=datetime.now(timezone.utc))
    pg_session.add(attempt)
    pg_session.flush()
    progress = AttemptModuleProgress(attempt_id=attempt.id, module_id=module.id, status=AttemptStatus.IN_PROGRESS, expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
    pg_session.add(progress)
    pg_session.commit()

    guard = ModuleAccessGuard(AttemptRepository(pg_session))
    try:
        guard.check_access(progress, attempt, student_id)
        assert False, "expected ModuleAccessDeniedException for expired module"
    except ModuleAccessDeniedException:
        pass
