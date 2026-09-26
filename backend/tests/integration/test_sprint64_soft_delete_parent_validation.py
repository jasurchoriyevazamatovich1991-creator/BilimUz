"""
Sprint 64 — C1. Soft-Delete Parent Validation integration tests, against
real PostgreSQL (Sprint 40's pg_session infrastructure).

Audit finding (Sprint 63/64 audits): ExamSectionRepository.get_by_id,
ExamModuleRepository.get_by_id, QuestionGroupRepository.get_by_id never
filtered deleted_at, unlike their own list_* methods and unlike
TestRepository.get_by_id (which does). The FK-validation call sites used
when creating/updating an ExamModule, QuestionGroup, or assigning a
Question to a section/module/group all called this unfiltered getter, so
a soft-deleted parent still passed validation as if it existed.

Fix: new get_active_by_id() methods added to ExamSectionRepository,
ExamModuleRepository, QuestionGroupRepository (excluding deleted_at rows),
used ONLY at the specific FK-validation call sites listed in the Sprint 64
prompt:
  - ExamModuleService.create_module
  - QuestionGroupService._validate_module_belongs_to_test (also reached
    from QuestionGroupService.create_group and update_group's module_id
    PATCH path)
  - QuestionService._validate_assignment_fields (reached from
    update_question's section_id/module_id/group_id PATCH)

get_by_id() itself was deliberately left untouched everywhere else
(ModuleExecutionService's execution-flow reads of an already-assigned
module, and ExamModuleService.get_module/ExamSectionService.get_section/
QuestionGroupService.get_group, which already re-check .deleted_at
themselves right after calling it) — per the prompt's explicit
instruction not to change shared repository behavior for callers that
don't need it, and not to touch TestRepository (already correct).
"""
import uuid

import pytest

from app.modules.questions.exceptions import InvalidTestReferenceException as QuestionInvalidTestReferenceException
from app.modules.questions.models import Question
from app.modules.questions.repository import OptionRepository, QuestionRepository
from app.modules.questions.schemas import QuestionUpdateRequest
from app.modules.questions.service import QuestionService
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.exceptions import ExamModuleNotFoundException, ExamSectionNotFoundException, InvalidTestReferenceException
from app.modules.tests.models import ExamModule, ExamSection, QuestionGroup, Test
from app.modules.tests.repository import ExamModuleRepository, ExamSectionRepository, QuestionGroupRepository, TestRepository
from app.modules.tests.schemas import ExamModuleCreateRequest, QuestionGroupCreateRequest, QuestionGroupUpdateRequest
from app.modules.tests.service import ExamModuleService, QuestionGroupService
from app.modules.users.models import User, UserStatus


def _make_actor(pg_session) -> uuid.UUID:
    """A real, persisted User row — required because log_action() writes
    an audit_logs row with a FK on user_id; a bare uuid.uuid4() actor_id
    (as used transiently in some older, non-audited service paths) fails
    audit_logs' fk_audit_logs_user_id constraint under real Postgres."""
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name="Actor", last_name="S64", email=f"actor-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    pg_session.flush()
    return user.id


def _make_test(pg_session) -> Test:
    subject = Subject(name=f"S64-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Sprint64 Soft-Delete", duration=60, question_count=0, status="published")
    pg_session.add(test)
    pg_session.flush()
    return test


def _module_service(pg_session) -> ExamModuleService:
    return ExamModuleService(ExamModuleRepository(pg_session), ExamSectionRepository(pg_session))


def _group_service(pg_session) -> QuestionGroupService:
    return QuestionGroupService(
        QuestionGroupRepository(pg_session), TestRepository(pg_session),
        ExamModuleRepository(pg_session), ExamSectionRepository(pg_session),
    )


def _question_service(pg_session) -> QuestionService:
    return QuestionService(
        QuestionRepository(pg_session), TestRepository(pg_session),
        ExamSectionRepository(pg_session), ExamModuleRepository(pg_session), QuestionGroupRepository(pg_session),
    )


# --- A: create module under active section -> success ---

def test_create_module_under_active_section_succeeds(pg_session):
    test = _make_test(pg_session)
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.commit()

    service = _module_service(pg_session)
    module = service.create_module(ExamModuleCreateRequest(section_id=section.id, name="Module 1", order_number=0), actor_id=_make_actor(pg_session))
    assert module.section_id == section.id


# --- B: soft-delete section -> create module under it -> rejected ---

def test_create_module_under_soft_deleted_section_rejected(pg_session):
    test = _make_test(pg_session)
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.commit()

    section_repo = ExamSectionRepository(pg_session)
    section_repo.update(section, {"deleted_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)})
    pg_session.commit()

    service = _module_service(pg_session)
    with pytest.raises(ExamSectionNotFoundException):
        service.create_module(ExamModuleCreateRequest(section_id=section.id, name="Module X", order_number=0), actor_id=_make_actor(pg_session))


# --- C: create group under active module -> success ---

def test_create_group_under_active_module_succeeds(pg_session):
    test = _make_test(pg_session)
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module = ExamModule(section_id=section.id, name="Module", order_number=0)
    pg_session.add(module)
    pg_session.commit()

    service = _group_service(pg_session)
    group = service.create_group(
        QuestionGroupCreateRequest(test_id=test.id, module_id=module.id, title="G", order_number=0), actor_id=_make_actor(pg_session),
    )
    assert group.module_id == module.id


# --- D: soft-delete module -> create group under it -> rejected ---

def test_create_group_under_soft_deleted_module_rejected(pg_session):
    test = _make_test(pg_session)
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module = ExamModule(section_id=section.id, name="Module", order_number=0)
    pg_session.add(module)
    pg_session.commit()

    module_repo = ExamModuleRepository(pg_session)
    module_repo.update(module, {"deleted_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)})
    pg_session.commit()

    service = _group_service(pg_session)
    with pytest.raises(ExamModuleNotFoundException):
        service.create_group(
            QuestionGroupCreateRequest(test_id=test.id, module_id=module.id, title="G", order_number=0), actor_id=_make_actor(pg_session),
        )


# --- Also verify update_group's PATCH path rejects a soft-deleted module ---

def test_update_group_module_reassignment_to_soft_deleted_module_rejected(pg_session):
    test = _make_test(pg_session)
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module = ExamModule(section_id=section.id, name="Module", order_number=0)
    pg_session.add(module)
    pg_session.commit()

    module_repo = ExamModuleRepository(pg_session)
    module_repo.update(module, {"deleted_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)})
    pg_session.commit()

    group_service = _group_service(pg_session)
    group = group_service.create_group(
        QuestionGroupCreateRequest(test_id=test.id, module_id=None, title="G", order_number=0), actor_id=_make_actor(pg_session),
    )

    with pytest.raises(ExamModuleNotFoundException):
        group_service.update_group(group.id, QuestionGroupUpdateRequest(module_id=module.id), actor_id=_make_actor(pg_session))


# --- E: assign question to active group -> success ---

def test_assign_question_to_active_group_succeeds(pg_session):
    test = _make_test(pg_session)
    question = Question(test_id=test.id, question_text="Q", question_type="single_choice", score=1)
    pg_session.add(question)
    pg_session.flush()

    group_service = _group_service(pg_session)
    group = group_service.create_group(QuestionGroupCreateRequest(test_id=test.id, module_id=None, title="G", order_number=0), actor_id=_make_actor(pg_session))
    pg_session.commit()

    question_service = _question_service(pg_session)
    updated = question_service.update_question(question.id, QuestionUpdateRequest(group_id=group.id), actor_id=_make_actor(pg_session))
    assert updated.group_id == group.id


# --- F: soft-delete group -> assign/update question to it -> rejected ---

def test_assign_question_to_soft_deleted_group_rejected(pg_session):
    test = _make_test(pg_session)
    question = Question(test_id=test.id, question_text="Q", question_type="single_choice", score=1)
    pg_session.add(question)
    pg_session.flush()

    group_service = _group_service(pg_session)
    group = group_service.create_group(QuestionGroupCreateRequest(test_id=test.id, module_id=None, title="G", order_number=0), actor_id=_make_actor(pg_session))
    pg_session.commit()

    group_repo = QuestionGroupRepository(pg_session)
    group_repo.soft_delete(group)
    pg_session.commit()

    question_service = _question_service(pg_session)
    with pytest.raises(QuestionInvalidTestReferenceException):
        question_service.update_question(question.id, QuestionUpdateRequest(group_id=group.id), actor_id=_make_actor(pg_session))


# --- Additional: soft-deleted ExamSection rejected via Question PATCH section_id ---

def test_assign_question_to_soft_deleted_section_rejected(pg_session):
    test = _make_test(pg_session)
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    question = Question(test_id=test.id, question_text="Q", question_type="single_choice", score=1)
    pg_session.add(question)
    pg_session.commit()

    section_repo = ExamSectionRepository(pg_session)
    section_repo.update(section, {"deleted_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)})
    pg_session.commit()

    question_service = _question_service(pg_session)
    with pytest.raises(QuestionInvalidTestReferenceException):
        question_service.update_question(question.id, QuestionUpdateRequest(section_id=section.id), actor_id=_make_actor(pg_session))


# --- Additional: soft-deleted ExamModule rejected via Question PATCH module_id ---

def test_assign_question_to_soft_deleted_module_rejected(pg_session):
    test = _make_test(pg_session)
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module = ExamModule(section_id=section.id, name="Module", order_number=0)
    pg_session.add(module)
    pg_session.flush()
    question = Question(test_id=test.id, question_text="Q", question_type="single_choice", score=1)
    pg_session.add(question)
    pg_session.commit()

    module_repo = ExamModuleRepository(pg_session)
    module_repo.update(module, {"deleted_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)})
    pg_session.commit()

    question_service = _question_service(pg_session)
    with pytest.raises(QuestionInvalidTestReferenceException):
        question_service.update_question(question.id, QuestionUpdateRequest(module_id=module.id), actor_id=_make_actor(pg_session))


# --- Regression: existing active-parent / cross-test validation behavior unchanged ---

def test_existing_cross_test_validation_still_rejects_foreign_section(pg_session):
    """Unrelated-test guard (pre-existing behavior) must remain intact:
    a section belonging to a DIFFERENT (active) test is still rejected,
    same as before this sprint — this is not a soft-delete case at all."""
    test1 = _make_test(pg_session)
    test2 = _make_test(pg_session)
    foreign_section = ExamSection(test_id=test2.id, name="Foreign", order_number=0)
    pg_session.add(foreign_section)
    question = Question(test_id=test1.id, question_text="Q", question_type="single_choice", score=1)
    pg_session.add(question)
    pg_session.commit()

    question_service = _question_service(pg_session)
    with pytest.raises(QuestionInvalidTestReferenceException):
        question_service.update_question(question.id, QuestionUpdateRequest(section_id=foreign_section.id), actor_id=_make_actor(pg_session))


def test_existing_active_parent_group_assignment_still_succeeds_after_fix(pg_session):
    """Regression: an active QuestionGroup with module_id=None (test-scoped,
    the normal case) is still accepted exactly as before — the fix must not
    reject any legitimate active reference."""
    test = _make_test(pg_session)
    question = Question(test_id=test.id, question_text="Q", question_type="single_choice", score=1)
    pg_session.add(question)
    pg_session.flush()

    group_service = _group_service(pg_session)
    group = group_service.create_group(QuestionGroupCreateRequest(test_id=test.id, module_id=None, title="G", order_number=0), actor_id=_make_actor(pg_session))
    pg_session.commit()

    question_service = _question_service(pg_session)
    updated = question_service.update_question(question.id, QuestionUpdateRequest(group_id=group.id), actor_id=_make_actor(pg_session))
    assert updated.group_id == group.id
