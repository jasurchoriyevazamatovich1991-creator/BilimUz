"""
Sprint 78 — shuffle-aware QuestionGroup ordering/stimulus contiguity,
against real PostgreSQL (Sprint 40's infrastructure — pg_session,
TEST_DATABASE_URL).

Scope: the ONE deferred finding from Sprint 77's audit —
`Test.shuffle_questions=True` combined with `QuestionGroup`s could
scatter a group's questions non-contiguously, since the old
`build_question_order()` was a plain `random.shuffle` with no group
awareness. Fixed at the single authoritative place question order is
ever generated for a non-modular test: `AttemptService.start_attempt()`
(see validators.build_question_order()'s own Sprint 78 docstring for
why the modular per-module path, which already always passes
shuffle=False, needed no change).

These tests exercise the real `start_attempt()` -> `get_attempt_detail()`
round trip (not the pure validators.py unit tests, which already cover
the algorithm itself in test_attempt_validators.py) specifically to
prove the end-to-end wiring (group_id is read from real Question rows,
no extra query, persisted correctly, survives resume) and that nothing
else (scoring, modular boundaries, soft-delete handling) regressed.

Matches this project's existing integration-test style for this engine
(see test_sprint77_question_group_student_delivery.py,
test_sprint76_module_timer_contract.py): AttemptService constructed
directly with real repositories, not through FastAPI's DI.
"""
import uuid
from datetime import datetime, timezone

import pytest

from app.modules.attempts.module_execution_service import ModuleExecutionService
from app.modules.attempts.repository import AnswerRepository, AttemptModuleProgressRepository, AttemptRepository
from app.modules.attempts.service import AttemptService
from app.modules.questions.models import Question, QuestionOption
from app.modules.questions.repository import OptionRepository, QuestionRepository
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import ExamModule, ExamSection, QuestionGroup, Test
from app.modules.tests.repository import ExamModuleRepository, ExamSectionRepository, QuestionGroupRepository, TestRepository
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
        ExamSectionRepository(pg_session),
        QuestionGroupRepository(pg_session),
    )


def _make_test(pg_session, title="T", shuffle=True) -> Test:
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title=title, duration=60, question_count=0, status="published", shuffle_questions=shuffle)
    pg_session.add(test)
    pg_session.flush()
    return test


def _make_group(pg_session, test_id, module_id=None, title="Passage", stimulus="stim", order=0) -> QuestionGroup:
    g = QuestionGroup(test_id=test_id, module_id=module_id, title=title, stimulus_text=stimulus, order_number=order)
    pg_session.add(g)
    pg_session.flush()
    return g


def _make_question(pg_session, test_id, module_id=None, group_id=None, text="Q", deleted=False) -> Question:
    q = Question(test_id=test_id, question_text=text, question_type="single_choice", score=1, module_id=module_id, group_id=group_id)
    pg_session.add(q)
    pg_session.flush()
    correct = QuestionOption(question_id=q.id, option_text="A", is_correct=True)
    wrong = QuestionOption(question_id=q.id, option_text="B", is_correct=False)
    pg_session.add_all([correct, wrong])
    pg_session.flush()
    if deleted:
        q.deleted_at = datetime.now(timezone.utc)
        pg_session.flush()
    return q


def _find_blocks(ordered_ids: list[uuid.UUID], id_to_group: dict[uuid.UUID, uuid.UUID | None]) -> list[list[uuid.UUID]]:
    blocks: list[list[uuid.UUID]] = []
    for qid in ordered_ids:
        gid = id_to_group.get(qid)
        if gid is not None and blocks and id_to_group.get(blocks[-1][-1]) == gid:
            blocks[-1].append(qid)
        else:
            blocks.append([qid])
    return blocks


# --- 1: shuffle=False preserves existing (unordered-query) order -------

def test_shuffle_false_preserves_insertion_order_even_with_groups(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session, shuffle=False)
    group = _make_group(pg_session, test.id)
    q1 = _make_question(pg_session, test.id, group_id=group.id, text="Q1")
    q2 = _make_question(pg_session, test.id, group_id=None, text="Q2")
    q3 = _make_question(pg_session, test.id, group_id=group.id, text="Q3")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    assert attempt.question_order == [q1.id, q2.id, q3.id]


# --- 2/3/4/5/6: shuffle=True keeps every group contiguous ---------------

def test_shuffle_true_keeps_single_group_contiguous_across_trials(pg_session):
    for _ in range(15):
        student_id = _make_student(pg_session)
        test = _make_test(pg_session, shuffle=True)
        group = _make_group(pg_session, test.id)
        a1 = _make_question(pg_session, test.id, group_id=group.id, text="A1")
        a2 = _make_question(pg_session, test.id, group_id=group.id, text="A2")
        a3 = _make_question(pg_session, test.id, group_id=group.id, text="A3")
        u1 = _make_question(pg_session, test.id, group_id=None, text="U1")
        pg_session.commit()

        service = _make_service(pg_session)
        attempt = service.start_attempt(test.id, student_id)
        pg_session.commit()

        order = attempt.question_order
        assert set(order) == {a1.id, a2.id, a3.id, u1.id}
        id_to_group = {a1.id: group.id, a2.id: group.id, a3.id: group.id, u1.id: None}
        blocks = _find_blocks(order, id_to_group)
        a_block = next(b for b in blocks if a1.id in b)
        assert a_block == [a1.id, a2.id, a3.id]  # never split, internal order preserved


def test_shuffle_true_multiple_groups_and_ungrouped_each_stay_separate_blocks(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session, shuffle=True)
    group_a = _make_group(pg_session, test.id, title="A", order=0)
    group_b = _make_group(pg_session, test.id, title="B", order=1)
    a1 = _make_question(pg_session, test.id, group_id=group_a.id, text="A1")
    a2 = _make_question(pg_session, test.id, group_id=group_a.id, text="A2")
    b1 = _make_question(pg_session, test.id, group_id=group_b.id, text="B1")
    b2 = _make_question(pg_session, test.id, group_id=group_b.id, text="B2")
    u1 = _make_question(pg_session, test.id, group_id=None, text="U1")
    u2 = _make_question(pg_session, test.id, group_id=None, text="U2")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    order = attempt.question_order
    assert set(order) == {a1.id, a2.id, b1.id, b2.id, u1.id, u2.id}
    id_to_group = {a1.id: group_a.id, a2.id: group_a.id, b1.id: group_b.id, b2.id: group_b.id, u1.id: None, u2.id: None}
    blocks = _find_blocks(order, id_to_group)
    assert sorted(len(b) for b in blocks) == [1, 1, 2, 2]
    a_block = next(b for b in blocks if a1.id in b)
    b_block = next(b for b in blocks if b1.id in b)
    assert a_block == [a1.id, a2.id]
    assert b_block == [b1.id, b2.id]


# --- 7: single-question group -------------------------------------------

def test_shuffle_true_single_question_group_is_valid(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session, shuffle=True)
    group = _make_group(pg_session, test.id)
    q1 = _make_question(pg_session, test.id, group_id=group.id, text="Q1")
    q2 = _make_question(pg_session, test.id, group_id=None, text="Q2")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    assert set(attempt.question_order) == {q1.id, q2.id}


# --- 8: soft-deleted question excluded ------------------------------------

def test_soft_deleted_question_excluded_from_order_and_grouping(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session, shuffle=True)
    group = _make_group(pg_session, test.id)
    a1 = _make_question(pg_session, test.id, group_id=group.id, text="A1")
    a2_deleted = _make_question(pg_session, test.id, group_id=group.id, text="A2-deleted", deleted=True)
    a3 = _make_question(pg_session, test.id, group_id=group.id, text="A3")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    assert a2_deleted.id not in attempt.question_order
    assert set(attempt.question_order) == {a1.id, a3.id}


# --- 9: soft-deleted group handled safely (contiguity kept, stimulus suppressed) ---

def test_soft_deleted_group_keeps_questions_contiguous_but_hides_stimulus(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session, shuffle=True)
    group = _make_group(pg_session, test.id, stimulus="secret stimulus")
    a1 = _make_question(pg_session, test.id, group_id=group.id, text="A1")
    a2 = _make_question(pg_session, test.id, group_id=group.id, text="A2")
    u1 = _make_question(pg_session, test.id, group_id=None, text="U1")
    pg_session.commit()
    group.deleted_at = datetime.now(timezone.utc)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    order = attempt.question_order
    id_to_group = {a1.id: group.id, a2.id: group.id, u1.id: None}
    blocks = _find_blocks(order, id_to_group)
    a_block = next(b for b in blocks if a1.id in b)
    assert a_block == [a1.id, a2.id]  # still contiguous even though the group is deleted

    detail = service.get_attempt_detail(attempt.id, student_id)
    by_id = {qv.id: qv for qv in detail.questions}
    assert by_id[a1.id].stimulus_text is None  # Sprint 77's suppression still applies
    assert by_id[a1.id].group_id is None


# --- 10: modular boundaries unaffected (regression) -----------------------

def test_modular_module_groups_never_mix_regardless_of_shuffle(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session, shuffle=True)  # shuffle on, but modules bypass it entirely
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0, duration=10)
    module2 = ExamModule(section_id=section.id, name="Module 2", order_number=1, duration=10)
    pg_session.add_all([module1, module2])
    pg_session.flush()
    group1 = _make_group(pg_session, test.id, module_id=module1.id, title="M1", order=0)
    group2 = _make_group(pg_session, test.id, module_id=module2.id, title="M2", order=1)
    m1q1 = _make_question(pg_session, test.id, module_id=module1.id, group_id=group1.id, text="M1Q1")
    m1q2 = _make_question(pg_session, test.id, module_id=module1.id, group_id=group1.id, text="M1Q2")
    m2q1 = _make_question(pg_session, test.id, module_id=module2.id, group_id=group2.id, text="M2Q1")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    assert detail.module_id == module1.id
    delivered_ids = {qv.id for qv in detail.questions}
    assert delivered_ids == {m1q1.id, m1q2.id}
    assert m2q1.id not in delivered_ids  # module 2's question never mixes into module 1's order


# --- 11/12: existing attempt order unchanged / resume preserves order ----

def test_existing_attempt_question_order_never_regenerated_on_resume(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session, shuffle=True)
    group = _make_group(pg_session, test.id)
    for i in range(6):
        _make_question(pg_session, test.id, group_id=group.id if i % 2 == 0 else None, text=f"Q{i}")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()
    original_order = list(attempt.question_order)

    first = service.get_attempt_detail(attempt.id, student_id)
    second = service.get_attempt_detail(attempt.id, student_id)  # simulated refresh
    assert [qv.id for qv in first.questions] == original_order
    assert [qv.id for qv in second.questions] == original_order


# --- 13: scoring unaffected by ordering ------------------------------------

def test_scoring_unaffected_by_group_aware_shuffle(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session, shuffle=True)
    group = _make_group(pg_session, test.id)
    q1 = _make_question(pg_session, test.id, group_id=group.id, text="Q1")
    q2 = _make_question(pg_session, test.id, group_id=group.id, text="Q2")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    # Answer both correctly regardless of their delivered order.
    for q in (q1, q2):
        correct_option = next(o for o in pg_session.query(QuestionOption).filter(QuestionOption.question_id == q.id) if o.is_correct)
        service.save_answer(attempt.id, student_id, q.id, selected_option=correct_option.id)
    pg_session.commit()

    result = service.submit_attempt(attempt.id, student_id)
    pg_session.commit()
    assert result.correct_count == 2
    assert result.percentage == 100.0


# --- 14: repeated generation never violates invariants ---------------------

def test_repeated_start_attempt_calls_each_independently_valid(pg_session):
    test = _make_test(pg_session, shuffle=True)
    group = _make_group(pg_session, test.id)
    q1 = _make_question(pg_session, test.id, group_id=group.id, text="Q1")
    q2 = _make_question(pg_session, test.id, group_id=group.id, text="Q2")
    q3 = _make_question(pg_session, test.id, group_id=None, text="Q3")
    pg_session.commit()

    service = _make_service(pg_session)
    id_to_group = {q1.id: group.id, q2.id: group.id, q3.id: None}
    for _ in range(10):
        student_id = _make_student(pg_session)
        pg_session.commit()
        attempt = service.start_attempt(test.id, student_id)
        pg_session.commit()
        order = attempt.question_order
        assert set(order) == {q1.id, q2.id, q3.id}
        blocks = _find_blocks(order, id_to_group)
        a_block = next(b for b in blocks if q1.id in b)
        assert a_block == [q1.id, q2.id]
