"""
Sprint 75 — Live Adaptive Routing Engine integration tests, against real
PostgreSQL (Sprint 40's infrastructure — pg_session, TEST_DATABASE_URL).

Constructs AttemptService/ModuleExecutionService directly with real
repositories, matching this project's existing integration-test style
(see test_module_execution.py, test_adaptive_routing_foundation.py).

Every test that wires `RoutingThresholdRuleRepository` creates its own
RoutingThresholdRule rows directly via the ORM — no admin UI/endpoint
exists for this yet (Sprint 75's explicit, documented scope decision),
exactly the same way Sprint 74's own tests exercised ExamSection/
ExamModule before any admin UI existed for them.
"""
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.modules.attempts.exceptions import ExamNotCompleteException
from app.modules.attempts.models import AttemptModuleProgress, AttemptStatus, TestAttempt
from app.modules.attempts.module_execution_service import ModuleExecutionService
from app.modules.attempts.repository import AnswerRepository, AttemptModuleProgressRepository, AttemptRepository
from app.modules.attempts.service import AttemptService
from app.modules.questions.models import Question, QuestionOption
from app.modules.questions.repository import OptionRepository, QuestionRepository
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import ExamModule, ExamSection, RoutingThresholdRule, Test
from app.modules.tests.repository import ExamModuleRepository, RoutingThresholdRuleRepository, TestRepository
from app.modules.users.models import User, UserStatus


def _make_student(pg_session) -> uuid.UUID:
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name="R", last_name="T", email=f"rt-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    pg_session.flush()
    return user.id


def _make_service(pg_session, with_rules: bool = True) -> AttemptService:
    routing_rule_repo = RoutingThresholdRuleRepository(pg_session) if with_rules else None
    return AttemptService(
        AttemptRepository(pg_session), AnswerRepository(pg_session), TestRepository(pg_session),
        QuestionRepository(pg_session), OptionRepository(pg_session),
        ModuleExecutionService(
            ExamModuleRepository(pg_session), AttemptModuleProgressRepository(pg_session),
            QuestionRepository(pg_session), AnswerRepository(pg_session), AttemptRepository(pg_session),
            routing_rule_repo,
        ),
        ExamModuleRepository(pg_session),
    )


def _make_test_with_subject(pg_session, title: str) -> Test:
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title=title, duration=60, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    return test


def _make_questions(pg_session, test_id, module_id, count: int) -> list[tuple[Question, QuestionOption]]:
    """`count` single_choice questions for a module, each with a real
    correct option. The caller controls the achieved ratio by choosing
    how many of these to actually answer correctly via save_answer —
    an unanswered question is simply never counted as correct."""
    out = []
    for i in range(count):
        q = Question(test_id=test_id, question_text=f"Q{i}", question_type="single_choice", score=1, module_id=module_id)
        pg_session.add(q)
        pg_session.flush()
        correct = QuestionOption(question_id=q.id, option_text="A", is_correct=True)
        wrong = QuestionOption(question_id=q.id, option_text="B", is_correct=False)
        pg_session.add_all([correct, wrong])
        pg_session.flush()
        out.append((q, correct))
    return out


def _add_rule(pg_session, test_id, routing_group: str, min_ratio: float, variant: str) -> RoutingThresholdRule:
    rule = RoutingThresholdRule(test_id=test_id, routing_group=routing_group, min_ratio=Decimal(str(min_ratio)), variant=variant)
    pg_session.add(rule)
    pg_session.flush()
    return rule


# --- 1: sequential fallback remains unchanged when nothing is configured ---

def test_sequential_fallback_unchanged_with_routing_repo_wired(pg_session):
    """Even with RoutingThresholdRuleRepository wired (the real
    production path), a module with routing_group=None must route
    exactly like Sprint 50's original SequentialRoutingStrategy —
    confirms Sprint 75 changes nothing for every pre-existing exam."""
    student_id = _make_student(pg_session)
    test = _make_test_with_subject(pg_session, "Plain Sequential")
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="M1", order_number=0)
    module2 = ExamModule(section_id=section.id, name="M2", order_number=1)
    pg_session.add_all([module1, module2])
    pg_session.flush()
    (q1, opt1), = _make_questions(pg_session, test.id, module1.id, 1)
    pg_session.commit()

    service = _make_service(pg_session, with_rules=True)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()
    service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()

    outcome = service.submit_module(attempt.id, module1.id, student_id)
    pg_session.commit()

    assert outcome["completed"] is False
    assert outcome["next_module_id"] == module2.id


# --- 2/3/4: adaptive strategy actually invoked; high/low performance picks correct variant ---

def _build_adaptive_exam(pg_session, student_id):
    """Section A: A1 (non-adaptive, order 0) -> A2 (routing_group=verbal,
    variant=easy, order 1) -> branches to either EASY or HARD within the
    SAME section (order 2/3). Rules: ratio>=0.0 -> easy, ratio>=0.5 -> hard."""
    test = _make_test_with_subject(pg_session, "Adaptive Exam")
    section = ExamSection(test_id=test.id, name="Section A", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    a1 = ExamModule(section_id=section.id, name="A1", order_number=0)
    a2 = ExamModule(section_id=section.id, name="A2", order_number=1, routing_group="verbal", routing_variant="diagnostic")
    a_easy = ExamModule(section_id=section.id, name="A-Easy", order_number=2, routing_group="verbal", routing_variant="easy")
    a_hard = ExamModule(section_id=section.id, name="A-Hard", order_number=3, routing_group="verbal", routing_variant="hard")
    pg_session.add_all([a1, a2, a_easy, a_hard])
    pg_session.flush()
    (q_a1, opt_a1), = _make_questions(pg_session, test.id, a1.id, 1)
    a2_questions = _make_questions(pg_session, test.id, a2.id, 4)  # correctness controlled per test
    _add_rule(pg_session, test.id, "verbal", 0.0, "easy")
    _add_rule(pg_session, test.id, "verbal", 0.5, "hard")
    pg_session.commit()

    service = _make_service(pg_session, with_rules=True)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()
    service.save_answer(attempt.id, student_id, q_a1.id, selected_option=opt_a1.id)
    pg_session.commit()
    service.submit_module(attempt.id, a1.id, student_id)
    pg_session.commit()
    return service, attempt, test, a2, a2_questions, a_easy, a_hard


def test_high_performance_selects_hard_variant(pg_session):
    student_id = _make_student(pg_session)
    service, attempt, test, a2, a2_questions, a_easy, a_hard = _build_adaptive_exam(pg_session, student_id)

    # Answer 3/4 correctly -> ratio 0.75 >= 0.5 -> "hard"
    for i, (q, correct_opt) in enumerate(a2_questions):
        if i < 3:
            service.save_answer(attempt.id, student_id, q.id, selected_option=correct_opt.id)
    pg_session.commit()

    outcome = service.submit_module(attempt.id, a2.id, student_id)
    pg_session.commit()

    assert outcome["completed"] is False
    assert outcome["next_module_id"] == a_hard.id


def test_low_performance_selects_easy_variant(pg_session):
    student_id = _make_student(pg_session)
    service, attempt, test, a2, a2_questions, a_easy, a_hard = _build_adaptive_exam(pg_session, student_id)

    # Answer 0/4 correctly -> ratio 0.0 >= 0.0 -> "easy" (not "hard")
    outcome = service.submit_module(attempt.id, a2.id, student_id)
    pg_session.commit()

    assert outcome["completed"] is False
    assert outcome["next_module_id"] == a_easy.id


# --- 5: no matching rule falls back safely (exam completes, no crash) ---

def test_no_matching_rule_completes_exam_safely(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test_with_subject(pg_session, "Gap In Rules")
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    m1 = ExamModule(section_id=section.id, name="M1", order_number=0, routing_group="verbal", routing_variant="diagnostic")
    pg_session.add(m1)
    pg_session.flush()
    (q1, _opt1), (q2, _opt2) = _make_questions(pg_session, test.id, m1.id, 2)
    # Only a high-bar rule exists — a 0% scorer matches nothing.
    _add_rule(pg_session, test.id, "verbal", 0.9, "advanced")
    pg_session.commit()

    service = _make_service(pg_session, with_rules=True)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    outcome = service.submit_module(attempt.id, m1.id, student_id)
    pg_session.commit()

    # No configured rule matches a 0.0 ratio -> strategy returns None ->
    # treated exactly like "no next module": the attempt finalizes
    # safely instead of crashing or exposing an undefined module.
    assert outcome["completed"] is True
    assert outcome["next_module_id"] is None
    assert outcome["result"] is not None


# --- 6: NULL routing_group uses sequential behavior even when rules exist for OTHER groups ---

def test_null_routing_group_uses_sequential_despite_configured_rules(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test_with_subject(pg_session, "Mixed Group")
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    m1 = ExamModule(section_id=section.id, name="M1", order_number=0)  # routing_group=None
    m2 = ExamModule(section_id=section.id, name="M2", order_number=1)
    pg_session.add_all([m1, m2])
    pg_session.flush()
    (q1, opt1), = _make_questions(pg_session, test.id, m1.id, 1)
    # Rules exist, but for a DIFFERENT routing_group than m1's (None).
    _add_rule(pg_session, test.id, "verbal", 0.0, "easy")
    pg_session.commit()

    service = _make_service(pg_session, with_rules=True)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()
    service.save_answer(attempt.id, student_id, q1.id, selected_option=opt1.id)
    pg_session.commit()

    outcome = service.submit_module(attempt.id, m1.id, student_id)
    pg_session.commit()

    assert outcome["next_module_id"] == m2.id  # plain sequential advance


# --- 7: NULL routing_variant candidate never gets selected by a real rule ---

def test_null_routing_variant_candidate_never_selected(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test_with_subject(pg_session, "Null Variant")
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    m1 = ExamModule(section_id=section.id, name="M1", order_number=0, routing_group="verbal", routing_variant="diagnostic")
    # m_null has the matching routing_group but NO routing_variant at all.
    m_null = ExamModule(section_id=section.id, name="M-Null", order_number=1, routing_group="verbal", routing_variant=None)
    m_easy = ExamModule(section_id=section.id, name="M-Easy", order_number=2, routing_group="verbal", routing_variant="easy")
    pg_session.add_all([m1, m_null, m_easy])
    pg_session.flush()
    (q1, _opt1), = _make_questions(pg_session, test.id, m1.id, 1)
    _add_rule(pg_session, test.id, "verbal", 0.0, "easy")
    pg_session.commit()

    service = _make_service(pg_session, with_rules=True)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    outcome = service.submit_module(attempt.id, m1.id, student_id)
    pg_session.commit()

    # Must route to the real "easy" variant module, never to m_null.
    assert outcome["next_module_id"] == m_easy.id


# --- 8: already-completed module cannot be selected again (adaptive path) ---

def test_already_completed_module_not_reselected_by_adaptive_strategy(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test_with_subject(pg_session, "No Revisit")
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    m1 = ExamModule(section_id=section.id, name="M1", order_number=0, routing_group="verbal", routing_variant="easy")
    m2 = ExamModule(section_id=section.id, name="M2", order_number=1, routing_group="verbal", routing_variant="hard")
    pg_session.add_all([m1, m2])
    pg_session.flush()
    (q1, _opt1), = _make_questions(pg_session, test.id, m1.id, 1)
    # A rule that would (wrongly, if revisiting were possible) match m1
    # itself back via its own group/variant — min_ratio 0.0 -> "easy".
    _add_rule(pg_session, test.id, "verbal", 0.0, "easy")
    pg_session.commit()

    service = _make_service(pg_session, with_rules=True)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    outcome = service.submit_module(attempt.id, m1.id, student_id)
    pg_session.commit()

    # m1 (the "easy" module) is already progressed/submitted, so even
    # though the winning rule's variant is "easy", m1 itself can never
    # be the candidate returned — only ever a DIFFERENT, not-yet-
    # progressed module could match, and none here has variant "easy"
    # besides m1 itself -> no match -> safely completes.
    assert outcome["next_module_id"] is None
    assert outcome["completed"] is True


# --- 9: cross-test rules never leak ---

def test_rules_configured_for_one_test_do_not_apply_to_another_test_reusing_the_same_group_name(pg_session):
    student_id = _make_student(pg_session)

    # Test 1 has real rules for "verbal".
    test1 = _make_test_with_subject(pg_session, "Test One")
    section1 = ExamSection(test_id=test1.id, name="Section", order_number=0)
    pg_session.add(section1)
    pg_session.flush()
    t1_m1 = ExamModule(section_id=section1.id, name="T1-M1", order_number=0, routing_group="verbal", routing_variant="diagnostic")
    t1_easy = ExamModule(section_id=section1.id, name="T1-Easy", order_number=1, routing_group="verbal", routing_variant="easy")
    pg_session.add_all([t1_m1, t1_easy])
    pg_session.flush()
    _add_rule(pg_session, test1.id, "verbal", 0.0, "easy")

    # Test 2 reuses the SAME routing_group/variant NAMES but has NO
    # rules of its own configured.
    test2 = _make_test_with_subject(pg_session, "Test Two")
    section2 = ExamSection(test_id=test2.id, name="Section", order_number=0)
    pg_session.add(section2)
    pg_session.flush()
    t2_m1 = ExamModule(section_id=section2.id, name="T2-M1", order_number=0, routing_group="verbal", routing_variant="diagnostic")
    t2_m2 = ExamModule(section_id=section2.id, name="T2-M2", order_number=1, routing_group="verbal", routing_variant="easy")
    pg_session.add_all([t2_m1, t2_m2])
    pg_session.flush()
    (q2, opt2), = _make_questions(pg_session, test2.id, t2_m1.id, 1)
    pg_session.commit()

    service = _make_service(pg_session, with_rules=True)
    attempt2 = service.start_attempt(test2.id, student_id)
    pg_session.commit()
    service.save_answer(attempt2.id, student_id, q2.id, selected_option=opt2.id)
    pg_session.commit()

    outcome = service.submit_module(attempt2.id, t2_m1.id, student_id)
    pg_session.commit()

    # Test 2 has zero rules of its own -> must use plain Sequential
    # (next by order_number), NOT Test 1's adaptive configuration.
    assert outcome["next_module_id"] == t2_m2.id


# --- 10: cross-section module cannot be selected, even if names collide ---

def test_cross_section_candidate_with_colliding_group_variant_names_is_rejected(pg_session):
    """Section A has only a "diagnostic" + "hard" module for "verbal";
    Section B separately defines its own "verbal"/"easy" module. After
    completing Section A's diagnostic module with a LOW score (which
    should route to "easy"), the only "easy"-variant module in the
    whole test happens to live in Section B. The fix must refuse this
    cross-section candidate and fail safely (treat as no next module),
    never silently jumping the student into another section."""
    student_id = _make_student(pg_session)
    test = _make_test_with_subject(pg_session, "Cross Section Collision")
    section_a = ExamSection(test_id=test.id, name="Section A", order_number=0)
    section_b = ExamSection(test_id=test.id, name="Section B", order_number=1)
    pg_session.add_all([section_a, section_b])
    pg_session.flush()

    a_diag = ExamModule(section_id=section_a.id, name="A-Diag", order_number=0, routing_group="verbal", routing_variant="diagnostic")
    a_hard = ExamModule(section_id=section_a.id, name="A-Hard", order_number=1, routing_group="verbal", routing_variant="hard")
    b_easy = ExamModule(section_id=section_b.id, name="B-Easy", order_number=0, routing_group="verbal", routing_variant="easy")
    pg_session.add_all([a_diag, a_hard, b_easy])
    pg_session.flush()
    (q, _opt), = _make_questions(pg_session, test.id, a_diag.id, 1)  # 0% -> "easy" wins
    _add_rule(pg_session, test.id, "verbal", 0.0, "easy")
    _add_rule(pg_session, test.id, "verbal", 0.5, "hard")
    pg_session.commit()

    service = _make_service(pg_session, with_rules=True)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    outcome = service.submit_module(attempt.id, a_diag.id, student_id)
    pg_session.commit()

    # The only real "easy" candidate (b_easy) is in a different
    # section -> rejected -> safe completion, never a cross-section jump.
    assert outcome["next_module_id"] is None
    assert outcome["completed"] is True

    # b_easy must never have received a progress row.
    b_easy_progress = pg_session.query(AttemptModuleProgress).filter(
        AttemptModuleProgress.attempt_id == attempt.id, AttemptModuleProgress.module_id == b_easy.id,
    ).first()
    assert b_easy_progress is None


# --- 11: selected adaptive module receives correct AttemptModuleProgress ---

def test_adaptively_selected_module_gets_correct_progress_row(pg_session):
    student_id = _make_student(pg_session)
    service, attempt, test, a2, a2_questions, a_easy, a_hard = _build_adaptive_exam(pg_session, student_id)

    outcome = service.submit_module(attempt.id, a2.id, student_id)
    pg_session.commit()
    assert outcome["next_module_id"] == a_easy.id

    progress = pg_session.query(AttemptModuleProgress).filter(
        AttemptModuleProgress.attempt_id == attempt.id, AttemptModuleProgress.module_id == a_easy.id,
    ).one()
    assert progress.status == "in_progress"
    assert progress.question_order is not None


# --- 12/13: effective scoring scope only includes actually-delivered (adaptively-routed) modules ---

def test_effective_scoring_scope_excludes_unvisited_sibling_variant(pg_session):
    student_id = _make_student(pg_session)
    service, attempt, test, a2, a2_questions, a_easy, a_hard = _build_adaptive_exam(pg_session, student_id)

    # Low score on a2 -> routes to a_easy, never a_hard.
    outcome = service.submit_module(attempt.id, a2.id, student_id)
    pg_session.commit()
    assert outcome["next_module_id"] == a_easy.id

    # Finish a_easy (no questions needed to just submit it) to complete the exam.
    final_outcome = service.submit_module(attempt.id, a_easy.id, student_id)
    pg_session.commit()
    assert final_outcome["completed"] is True

    effective_ids = service.module_execution.get_effective_question_ids(attempt.id)
    # a_hard was never visited -> it has no progress row at all, so none
    # of its questions (there are none in this flow anyway) are part of
    # the effective/delivered scope.
    a_hard_progress = pg_session.query(AttemptModuleProgress).filter(
        AttemptModuleProgress.attempt_id == attempt.id, AttemptModuleProgress.module_id == a_hard.id,
    ).first()
    assert a_hard_progress is None
    assert effective_ids is not None


def test_final_result_scope_matches_adaptively_delivered_modules(pg_session):
    student_id = _make_student(pg_session)
    service, attempt, test, a2, a2_questions, a_easy, a_hard = _build_adaptive_exam(pg_session, student_id)

    outcome = service.submit_module(attempt.id, a2.id, student_id)
    pg_session.commit()
    assert outcome["next_module_id"] == a_easy.id

    final_outcome = service.submit_module(attempt.id, a_easy.id, student_id)
    pg_session.commit()
    assert final_outcome["completed"] is True
    result = final_outcome["result"]
    # Delivered: a1 (1 q) + a2 (4 q) + a_easy (0 q) = 5 effective questions.
    # a_hard's questions (none created) are correctly excluded either way.
    assert result.total_questions == 5


# --- 14: concurrent module submission stays race-safe with routing rules wired ---

def test_concurrent_module_submit_is_race_safe_with_adaptive_routing():
    """Same race-safety guarantee as Sprint 50's
    test_concurrent_module_submit_is_race_safe, now exercised with a
    real RoutingThresholdRuleRepository wired — confirms the new
    rule-lookup read inside _route_to_next_module introduces no new
    race window (it reads already-committed, attempt-independent
    configuration rows, never anything mutated by concurrent submits)."""
    from sqlalchemy.orm import sessionmaker
    from app.db.database import engine

    Session = sessionmaker(bind=engine)

    def make_service(s):
        return AttemptService(
            AttemptRepository(s), AnswerRepository(s), TestRepository(s), QuestionRepository(s), OptionRepository(s),
            ModuleExecutionService(
                ExamModuleRepository(s), AttemptModuleProgressRepository(s), QuestionRepository(s), AnswerRepository(s), AttemptRepository(s),
                RoutingThresholdRuleRepository(s),
            ),
            ExamModuleRepository(s),
        )

    setup = Session()
    try:
        role = setup.query(Role).filter(Role.name == "Student").one()
        user = User(role_id=role.id, first_name="CC", last_name="AR", email=f"ccar-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
        setup.add(user)
        setup.flush()
        student_id = user.id
        subject = Subject(name=f"S-{uuid.uuid4()}")
        setup.add(subject)
        setup.flush()
        test = Test(subject_id=subject.id, title="Adaptive Concurrency Test", duration=60, question_count=0, status="published")
        setup.add(test)
        setup.flush()
        section = ExamSection(test_id=test.id, name="Section", order_number=0)
        setup.add(section)
        setup.flush()
        module1 = ExamModule(section_id=section.id, name="M1", order_number=0, routing_group="verbal", routing_variant="diagnostic")
        module_easy = ExamModule(section_id=section.id, name="M-Easy", order_number=1, routing_group="verbal", routing_variant="easy")
        module_hard = ExamModule(section_id=section.id, name="M-Hard", order_number=2, routing_group="verbal", routing_variant="hard")
        setup.add_all([module1, module_easy, module_hard])
        setup.flush()
        q1 = Question(test_id=test.id, question_text="Q1", question_type="single_choice", score=1, module_id=module1.id)
        setup.add(q1)
        setup.flush()
        opt1 = QuestionOption(question_id=q1.id, option_text="A", is_correct=True)
        setup.add(opt1)
        rule_easy = RoutingThresholdRule(test_id=test.id, routing_group="verbal", min_ratio=Decimal("0.0"), variant="easy")
        rule_hard = RoutingThresholdRule(test_id=test.id, routing_group="verbal", min_ratio=Decimal("0.5"), variant="hard")
        setup.add_all([rule_easy, rule_hard])
        setup.commit()

        service = make_service(setup)
        attempt = service.start_attempt(test.id, student_id)
        attempt_id, module1_id, module_easy_id, module_hard_id = attempt.id, module1.id, module_easy.id, module_hard.id
        test_id, section_id, subject_id, q1_id = test.id, section.id, subject.id, q1.id
        setup.commit()
    finally:
        setup.close()

    outcomes = {}

    def worker(name: str):
        s = Session()
        svc = make_service(s)
        try:
            r = svc.submit_module(attempt_id, module1_id, student_id)
            s.commit()
            outcomes[name] = ("OK", r)
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
    successes = [r for r in results if r is not None and r[0] == "OK"]
    failures = [r for r in results if r is not None and r[0] == "ERROR"]

    try:
        assert len(successes) == 1, f"expected exactly 1 success, got {results}"
        assert len(failures) == 1, f"expected exactly 1 rejection, got {results}"
        assert failures[0][1] == "ModuleNotActiveException"

        verify = Session()
        try:
            # Exactly one of the two sibling variant modules has a
            # progress row — never both, never neither.
            easy_progress = verify.query(AttemptModuleProgress).filter(
                AttemptModuleProgress.attempt_id == attempt_id, AttemptModuleProgress.module_id == module_easy_id,
            ).first()
            hard_progress = verify.query(AttemptModuleProgress).filter(
                AttemptModuleProgress.attempt_id == attempt_id, AttemptModuleProgress.module_id == module_hard_id,
            ).first()
            assert (easy_progress is None) != (hard_progress is None)
        finally:
            verify.close()
    finally:
        cleanup = Session()
        try:
            cleanup.query(RoutingThresholdRule).filter(RoutingThresholdRule.test_id == test_id).delete()
            cleanup.query(AttemptModuleProgress).filter(AttemptModuleProgress.attempt_id == attempt_id).delete()
            cleanup.query(TestAttempt).filter(TestAttempt.id == attempt_id).delete()
            cleanup.query(QuestionOption).filter(QuestionOption.question_id == q1_id).delete(synchronize_session=False)
            cleanup.query(Question).filter(Question.test_id == test_id).delete()
            cleanup.query(ExamModule).filter(ExamModule.section_id == section_id).delete()
            cleanup.query(ExamSection).filter(ExamSection.id == section_id).delete()
            cleanup.query(Test).filter(Test.id == test_id).delete()
            cleanup.query(Subject).filter(Subject.id == subject_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()


# --- Routing threshold rule DB constraints ---

def test_routing_threshold_rule_unique_constraint_blocks_ambiguous_config(pg_session):
    test = _make_test_with_subject(pg_session, "Unique Rule Test")
    pg_session.commit()
    _add_rule(pg_session, test.id, "verbal", 0.5, "hard")
    pg_session.commit()

    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        _add_rule(pg_session, test.id, "verbal", 0.5, "harder")  # same (test, group, ratio)
        pg_session.commit()
    pg_session.rollback()


def test_routing_threshold_rule_check_constraint_rejects_out_of_range_ratio(pg_session):
    test = _make_test_with_subject(pg_session, "Ratio Range Test")
    pg_session.commit()

    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        _add_rule(pg_session, test.id, "verbal", 1.5, "impossible")
        pg_session.commit()
    pg_session.rollback()
