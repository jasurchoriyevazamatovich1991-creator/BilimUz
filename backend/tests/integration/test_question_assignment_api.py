"""
Sprint 52 — Question Assignment API integration tests, against real
PostgreSQL (Sprint 40's infrastructure — pg_session, TEST_DATABASE_URL).

Tests QuestionService.update_question() directly (matching this
project's existing integration-test style — see
test_exam_config_api.py) rather than through FastAPI's HTTP layer,
since RBAC itself is an already-proven, unchanged, project-wide
mechanism this sprint reuses as-is.
"""
import uuid

import pytest

from app.modules.questions.exceptions import InvalidTestReferenceException
from app.modules.questions.models import Question
from app.modules.questions.repository import QuestionRepository
from app.modules.questions.schemas import QuestionUpdateRequest
from app.modules.questions.service import QuestionService
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import ExamModule, ExamSection, QuestionGroup, Test
from app.modules.tests.repository import ExamModuleRepository, ExamSectionRepository, QuestionGroupRepository, TestRepository
from app.modules.users.models import User, UserStatus


def _make_admin(pg_session) -> uuid.UUID:
    role = pg_session.query(Role).filter(Role.name == "Admin").one()
    user = User(role_id=role.id, first_name="A", last_name="B", email=f"a-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    pg_session.flush()
    return user.id


def _make_test(pg_session, title="T") -> Test:
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title=title, duration=30, question_count=0, status="draft")
    pg_session.add(test)
    pg_session.flush()
    return test


def _make_question(pg_session, test_id) -> Question:
    q = Question(test_id=test_id, question_text="Q?", question_type="single_choice", score=1)
    pg_session.add(q)
    pg_session.flush()
    return q


def _service(pg_session) -> QuestionService:
    return QuestionService(
        QuestionRepository(pg_session), TestRepository(pg_session),
        ExamSectionRepository(pg_session), ExamModuleRepository(pg_session), QuestionGroupRepository(pg_session),
    )


# --- A/B/C/D: successful assignments ---

def test_successful_section_assignment(pg_session):
    admin_id = _make_admin(pg_session)
    test = _make_test(pg_session)
    question = _make_question(pg_session, test.id)
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.commit()

    service = _service(pg_session)
    updated = service.update_question(question.id, QuestionUpdateRequest(section_id=section.id), admin_id)
    pg_session.commit()

    assert updated.section_id == section.id


def test_successful_module_assignment(pg_session):
    admin_id = _make_admin(pg_session)
    test = _make_test(pg_session)
    question = _make_question(pg_session, test.id)
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module = ExamModule(section_id=section.id, name="Module", order_number=0)
    pg_session.add(module)
    pg_session.commit()

    service = _service(pg_session)
    updated = service.update_question(question.id, QuestionUpdateRequest(module_id=module.id), admin_id)
    pg_session.commit()

    assert updated.module_id == module.id


def test_successful_group_assignment(pg_session):
    admin_id = _make_admin(pg_session)
    test = _make_test(pg_session)
    question = _make_question(pg_session, test.id)
    group = QuestionGroup(test_id=test.id, title="Passage", order_number=0)
    pg_session.add(group)
    pg_session.commit()

    service = _service(pg_session)
    updated = service.update_question(question.id, QuestionUpdateRequest(group_id=group.id), admin_id)
    pg_session.commit()

    assert updated.group_id == group.id


def test_successful_combined_assignment(pg_session):
    admin_id = _make_admin(pg_session)
    test = _make_test(pg_session)
    question = _make_question(pg_session, test.id)
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module = ExamModule(section_id=section.id, name="Module", order_number=0)
    pg_session.add(module)
    group = QuestionGroup(test_id=test.id, title="Passage", order_number=0, module_id=module.id)
    pg_session.add(group)
    pg_session.commit()

    service = _service(pg_session)
    updated = service.update_question(
        question.id, QuestionUpdateRequest(section_id=section.id, module_id=module.id, group_id=group.id), admin_id,
    )
    pg_session.commit()

    assert updated.section_id == section.id
    assert updated.module_id == module.id
    assert updated.group_id == group.id


# --- E/F/G: cross-test rejection ---

def test_cross_test_section_rejected(pg_session):
    admin_id = _make_admin(pg_session)
    test_a = _make_test(pg_session, "A")
    test_b = _make_test(pg_session, "B")
    question = _make_question(pg_session, test_a.id)
    section_b = ExamSection(test_id=test_b.id, name="Section B", order_number=0)
    pg_session.add(section_b)
    pg_session.commit()

    service = _service(pg_session)
    with pytest.raises(InvalidTestReferenceException):
        service.update_question(question.id, QuestionUpdateRequest(section_id=section_b.id), admin_id)


def test_cross_test_module_rejected(pg_session):
    admin_id = _make_admin(pg_session)
    test_a = _make_test(pg_session, "A")
    test_b = _make_test(pg_session, "B")
    question = _make_question(pg_session, test_a.id)
    section_b = ExamSection(test_id=test_b.id, name="Section B", order_number=0)
    pg_session.add(section_b)
    pg_session.flush()
    module_b = ExamModule(section_id=section_b.id, name="Module B", order_number=0)
    pg_session.add(module_b)
    pg_session.commit()

    service = _service(pg_session)
    with pytest.raises(InvalidTestReferenceException):
        service.update_question(question.id, QuestionUpdateRequest(module_id=module_b.id), admin_id)


def test_cross_test_group_rejected(pg_session):
    admin_id = _make_admin(pg_session)
    test_a = _make_test(pg_session, "A")
    test_b = _make_test(pg_session, "B")
    question = _make_question(pg_session, test_a.id)
    group_b = QuestionGroup(test_id=test_b.id, title="Group B", order_number=0)
    pg_session.add(group_b)
    pg_session.commit()

    service = _service(pg_session)
    with pytest.raises(InvalidTestReferenceException):
        service.update_question(question.id, QuestionUpdateRequest(group_id=group_b.id), admin_id)


# --- H/I: mismatch rejection ---

def test_section_module_mismatch_rejected(pg_session):
    admin_id = _make_admin(pg_session)
    test = _make_test(pg_session)
    question = _make_question(pg_session, test.id)
    section_a = ExamSection(test_id=test.id, name="A", order_number=0)
    section_b = ExamSection(test_id=test.id, name="B", order_number=1)
    pg_session.add_all([section_a, section_b])
    pg_session.flush()
    module_b = ExamModule(section_id=section_b.id, name="Module B", order_number=0)
    pg_session.add(module_b)
    pg_session.commit()

    service = _service(pg_session)
    with pytest.raises(InvalidTestReferenceException):
        service.update_question(
            question.id, QuestionUpdateRequest(section_id=section_a.id, module_id=module_b.id), admin_id,
        )


def test_group_module_mismatch_rejected(pg_session):
    admin_id = _make_admin(pg_session)
    test = _make_test(pg_session)
    question = _make_question(pg_session, test.id)
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module_a = ExamModule(section_id=section.id, name="Module A", order_number=0)
    module_b = ExamModule(section_id=section.id, name="Module B", order_number=1)
    pg_session.add_all([module_a, module_b])
    pg_session.flush()
    group_bound_to_a = QuestionGroup(test_id=test.id, title="Group", order_number=0, module_id=module_a.id)
    pg_session.add(group_bound_to_a)
    pg_session.commit()

    service = _service(pg_session)
    with pytest.raises(InvalidTestReferenceException):
        service.update_question(
            question.id, QuestionUpdateRequest(group_id=group_bound_to_a.id, module_id=module_b.id), admin_id,
        )


def test_group_with_no_module_plus_module_assignment_is_valid(pg_session):
    """A test-scoped group (module_id=None) may coexist with the
    question being assigned to a module — explicitly valid per
    Sprint 52's own rule."""
    admin_id = _make_admin(pg_session)
    test = _make_test(pg_session)
    question = _make_question(pg_session, test.id)
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module = ExamModule(section_id=section.id, name="Module", order_number=0)
    pg_session.add(module)
    group = QuestionGroup(test_id=test.id, title="Test-scoped group", order_number=0)  # module_id=None
    pg_session.add(group)
    pg_session.commit()

    service = _service(pg_session)
    updated = service.update_question(
        question.id, QuestionUpdateRequest(group_id=group.id, module_id=module.id), admin_id,
    )
    pg_session.commit()

    assert updated.group_id == group.id
    assert updated.module_id == module.id


# --- J: existing update compatibility ---

def test_existing_question_update_unaffected_by_sprint_52(pg_session):
    admin_id = _make_admin(pg_session)
    test = _make_test(pg_session)
    question = _make_question(pg_session, test.id)
    pg_session.commit()

    service = _service(pg_session)
    updated = service.update_question(question.id, QuestionUpdateRequest(question_text="New text"), admin_id)
    pg_session.commit()

    assert updated.question_text == "New text"
    assert updated.section_id is None
    assert updated.module_id is None
    assert updated.group_id is None


# --- K: explicit unassignment ---

def test_explicit_null_unassigns_section(pg_session):
    admin_id = _make_admin(pg_session)
    test = _make_test(pg_session)
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    question = Question(test_id=test.id, question_text="Q", question_type="single_choice", score=1, section_id=section.id)
    pg_session.add(question)
    pg_session.commit()

    service = _service(pg_session)
    updated = service.update_question(question.id, QuestionUpdateRequest(section_id=None), admin_id)
    pg_session.commit()

    # exclude_unset=True: section_id WAS explicitly supplied (as None)
    # in this request, so it's present in `updates` -> unassigned.
    assert updated.section_id is None


def test_omitted_field_leaves_existing_assignment_unchanged(pg_session):
    """The critical distinction from the test above: omitting the
    field entirely (not even setting it to None) must NOT unassign."""
    admin_id = _make_admin(pg_session)
    test = _make_test(pg_session)
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    question = Question(test_id=test.id, question_text="Q", question_type="single_choice", score=1, section_id=section.id)
    pg_session.add(question)
    pg_session.commit()

    service = _service(pg_session)
    updated = service.update_question(question.id, QuestionUpdateRequest(question_text="Only text changed"), admin_id)
    pg_session.commit()

    assert updated.section_id == section.id  # unchanged
    assert updated.question_text == "Only text changed"
