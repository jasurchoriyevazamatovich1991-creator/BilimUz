"""
Sprint 77 — QuestionGroup / stimulus_text student exam delivery, against
real PostgreSQL (Sprint 40's infrastructure — pg_session,
TEST_DATABASE_URL).

Scope: the ONE contract gap the Sprint 76 audit deferred —
QuestionForAttemptOut now additively carries group_id/group_title/
stimulus_text (AttemptService.get_attempt_detail() -> _to_question_view()),
populated via one batched QuestionGroupRepository.list_active_by_ids()
call keyed only by group_ids already present on questions scoped to
effective_question_order (the active module for a modular attempt, the
whole attempt otherwise — Sprint 57's existing security boundary,
untouched by this sprint). No new endpoint, no admin surface exposed to
students, no per-question group lookup (no N+1).

Matches this project's existing integration-test style for this engine
(see test_sprint76_module_timer_contract.py, test_sprint_a_module_metadata.py):
AttemptService constructed directly with real repositories, not through
FastAPI's DI.
"""
import uuid
from datetime import datetime, timezone

import pytest

from app.modules.attempts.exceptions import AttemptNotFoundException
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


def _make_service(pg_session, with_group_repo: bool = True) -> AttemptService:
    return AttemptService(
        AttemptRepository(pg_session), AnswerRepository(pg_session), TestRepository(pg_session),
        QuestionRepository(pg_session), OptionRepository(pg_session),
        ModuleExecutionService(
            ExamModuleRepository(pg_session), AttemptModuleProgressRepository(pg_session),
            QuestionRepository(pg_session), AnswerRepository(pg_session), AttemptRepository(pg_session),
        ),
        ExamModuleRepository(pg_session),
        ExamSectionRepository(pg_session),
        QuestionGroupRepository(pg_session) if with_group_repo else None,
    )


def _make_question(pg_session, test_id, module_id=None, group_id=None, text="Q") -> Question:
    q = Question(test_id=test_id, question_text=text, question_type="single_choice", score=1, module_id=module_id, group_id=group_id)
    pg_session.add(q)
    pg_session.flush()
    correct = QuestionOption(question_id=q.id, option_text="A", is_correct=True)
    wrong = QuestionOption(question_id=q.id, option_text="B", is_correct=False)
    pg_session.add_all([correct, wrong])
    pg_session.flush()
    return q


def _make_test(pg_session, title="T") -> Test:
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title=title, duration=60, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    return test


def _make_group(pg_session, test_id, module_id=None, title="Passage", stimulus="Once upon a time...", order=0) -> QuestionGroup:
    g = QuestionGroup(test_id=test_id, module_id=module_id, title=title, stimulus_text=stimulus, order_number=order)
    pg_session.add(g)
    pg_session.flush()
    return g


# --- 1/2/3: basic presence/absence ---

def test_ungrouped_question_has_no_group_fields(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    _make_question(pg_session, test.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    assert detail.questions[0].group_id is None
    assert detail.questions[0].group_title is None
    assert detail.questions[0].stimulus_text is None


def test_grouped_question_with_null_stimulus_text(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    group = _make_group(pg_session, test.id, title="Diagram set", stimulus=None)
    _make_question(pg_session, test.id, group_id=group.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    assert detail.questions[0].group_id == group.id
    assert detail.questions[0].group_title == "Diagram set"
    assert detail.questions[0].stimulus_text is None


def test_grouped_question_with_stimulus_text(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    group = _make_group(pg_session, test.id, title="Passage 1", stimulus="Reading passage body.")
    _make_question(pg_session, test.id, group_id=group.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    assert detail.questions[0].group_id == group.id
    assert detail.questions[0].group_title == "Passage 1"
    assert detail.questions[0].stimulus_text == "Reading passage body."


# --- 4/5: multiple questions sharing a group ---

def test_two_questions_same_group_share_identical_group_context(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    group = _make_group(pg_session, test.id, title="Passage 1", stimulus="Shared text")
    _make_question(pg_session, test.id, group_id=group.id, text="Q1")
    _make_question(pg_session, test.id, group_id=group.id, text="Q2")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    assert len(detail.questions) == 2
    for qv in detail.questions:
        assert qv.group_id == group.id
        assert qv.stimulus_text == "Shared text"


def test_five_questions_same_group(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    group = _make_group(pg_session, test.id, title="Passage 1", stimulus="Shared text")
    for i in range(5):
        _make_question(pg_session, test.id, group_id=group.id, text=f"Q{i}")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    assert len(detail.questions) == 5
    assert all(qv.group_id == group.id for qv in detail.questions)


# --- 6/7/8: group transitions ---

def test_group_a_to_group_b_transition(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    group_a = _make_group(pg_session, test.id, title="A", stimulus="stim-a", order=0)
    group_b = _make_group(pg_session, test.id, title="B", stimulus="stim-b", order=1)
    q1 = _make_question(pg_session, test.id, group_id=group_a.id, text="Q1")
    q2 = _make_question(pg_session, test.id, group_id=group_b.id, text="Q2")
    pg_session.commit()

    service = _make_service(pg_session)
    # Pin deterministic ordering (start_attempt may shuffle only if
    # test.shuffle_questions is True — default False here, but be
    # explicit about what this test actually asserts).
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    by_id = {qv.id: qv for qv in detail.questions}
    assert by_id[q1.id].group_id == group_a.id
    assert by_id[q2.id].group_id == group_b.id


def test_group_a_to_ungrouped_transition(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    group_a = _make_group(pg_session, test.id, title="A", stimulus="stim-a")
    q1 = _make_question(pg_session, test.id, group_id=group_a.id, text="Q1")
    q2 = _make_question(pg_session, test.id, group_id=None, text="Q2")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    by_id = {qv.id: qv for qv in detail.questions}
    assert by_id[q1.id].group_id == group_a.id
    assert by_id[q2.id].group_id is None


def test_ungrouped_to_group_a_transition(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    group_a = _make_group(pg_session, test.id, title="A", stimulus="stim-a")
    q1 = _make_question(pg_session, test.id, group_id=None, text="Q1")
    q2 = _make_question(pg_session, test.id, group_id=group_a.id, text="Q2")
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    by_id = {qv.id: qv for qv in detail.questions}
    assert by_id[q1.id].group_id is None
    assert by_id[q2.id].group_id == group_a.id


# --- 9: soft-deleted group never leaks ---

def test_soft_deleted_group_stimulus_does_not_leak(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    group = _make_group(pg_session, test.id, title="Deleted passage", stimulus="secret stimulus")
    _make_question(pg_session, test.id, group_id=group.id)
    pg_session.commit()
    group.deleted_at = datetime.now(timezone.utc)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    # Treated as fully ungrouped — not even the dangling group_id is
    # exposed (see QuestionForAttemptOut's Sprint 77 docstring).
    assert detail.questions[0].group_id is None
    assert detail.questions[0].group_title is None
    assert detail.questions[0].stimulus_text is None


# --- 10/11: module-boundary scoping (future module never leaks) ---

def test_future_module_group_stimulus_not_shown_while_module_1_active(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0, duration=10)
    module2 = ExamModule(section_id=section.id, name="Module 2", order_number=1, duration=10)
    pg_session.add_all([module1, module2])
    pg_session.flush()
    group1 = _make_group(pg_session, test.id, module_id=module1.id, title="M1 passage", stimulus="m1 stim", order=0)
    group2 = _make_group(pg_session, test.id, module_id=module2.id, title="M2 passage", stimulus="m2 stim (must not leak)", order=1)
    _make_question(pg_session, test.id, module_id=module1.id, group_id=group1.id)
    _make_question(pg_session, test.id, module_id=module2.id, group_id=group2.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    # Only module 1's question is ever in effective_question_order right
    # now — module 2's group can't appear, by construction, not by a
    # filter that could be bypassed.
    assert len(detail.questions) == 1
    assert detail.questions[0].group_id == group1.id
    assert detail.questions[0].stimulus_text == "m1 stim"
    assert all("m2 stim" not in (qv.stimulus_text or "") for qv in detail.questions)


def test_active_module_group_is_shown_after_routing_to_next_module(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module1 = ExamModule(section_id=section.id, name="Module 1", order_number=0, duration=10)
    module2 = ExamModule(section_id=section.id, name="Module 2", order_number=1, duration=10)
    pg_session.add_all([module1, module2])
    pg_session.flush()
    group1 = _make_group(pg_session, test.id, module_id=module1.id, title="M1 passage", stimulus="m1 stim", order=0)
    group2 = _make_group(pg_session, test.id, module_id=module2.id, title="M2 passage", stimulus="m2 stim", order=1)
    _make_question(pg_session, test.id, module_id=module1.id, group_id=group1.id)
    _make_question(pg_session, test.id, module_id=module2.id, group_id=group2.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    service.submit_module(attempt.id, module1.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    assert detail.module_id == module2.id
    assert len(detail.questions) == 1
    assert detail.questions[0].group_id == group2.id
    assert detail.questions[0].stimulus_text == "m2 stim"


# --- 12: resume ---

def test_resume_shows_same_group_context_as_before(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    group = _make_group(pg_session, test.id, title="Passage 1", stimulus="stim")
    _make_question(pg_session, test.id, group_id=group.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    first = service.get_attempt_detail(attempt.id, student_id)
    second = service.get_attempt_detail(attempt.id, student_id)  # simulates a page refresh
    assert first.questions[0].group_id == second.questions[0].group_id == group.id
    assert first.questions[0].stimulus_text == second.questions[0].stimulus_text == "stim"


# --- 14/15: non-modular exam and existing single-question flow unaffected ---

def test_non_modular_exam_group_delivery_works_without_module_concept(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    group = _make_group(pg_session, test.id, title="Passage 1", stimulus="stim")
    _make_question(pg_session, test.id, group_id=group.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    assert detail.module_id is None  # non-modular, unaffected by Sprint 77
    assert detail.questions[0].group_id == group.id


def test_existing_single_question_no_group_regression(pg_session):
    """A plain pre-Sprint-77-style attempt (no QuestionGroup ever
    created for this test) gets byte-identical QuestionForAttemptOut
    content except for the three new all-None fields."""
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    q = _make_question(pg_session, test.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    qv = detail.questions[0]
    assert qv.id == q.id
    assert qv.question_text == "Q"
    assert len(qv.options) == 2
    assert qv.group_id is None and qv.group_title is None and qv.stimulus_text is None


# --- Security: ownership/IDOR unaffected by the new enrichment ---

def test_foreign_attempt_access_still_raises_not_found(pg_session):
    owner_id = _make_student(pg_session)
    other_id = _make_student(pg_session)
    test = _make_test(pg_session)
    group = _make_group(pg_session, test.id, title="P", stimulus="s")
    _make_question(pg_session, test.id, group_id=group.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, owner_id)
    pg_session.commit()

    with pytest.raises(AttemptNotFoundException):
        service.get_attempt_detail(attempt.id, other_id)


def test_answer_key_never_present_on_grouped_question(pg_session):
    """Regression guard — the new fields are purely additive; is_correct
    was never on QuestionForAttemptOut/OptionForAttemptOut before this
    sprint and still isn't."""
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    group = _make_group(pg_session, test.id, title="P", stimulus="s")
    _make_question(pg_session, test.id, group_id=group.id)
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    qv = detail.questions[0]
    assert not hasattr(qv, "is_correct")
    for opt in qv.options:
        assert not hasattr(opt, "is_correct")


# --- Backward compatibility: legacy construction without group_repo ---

def test_legacy_construction_without_group_repo_leaves_group_fields_none(pg_session):
    student_id = _make_student(pg_session)
    test = _make_test(pg_session)
    group = _make_group(pg_session, test.id, title="P", stimulus="s")
    _make_question(pg_session, test.id, group_id=group.id)
    pg_session.commit()

    service = _make_service(pg_session, with_group_repo=False)
    attempt = service.start_attempt(test.id, student_id)
    pg_session.commit()

    detail = service.get_attempt_detail(attempt.id, student_id)
    assert detail.questions[0].group_id is None
    assert detail.questions[0].stimulus_text is None
