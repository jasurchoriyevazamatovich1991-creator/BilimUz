"""
Sprint 51 — Admin Exam Configuration API integration tests, against
real PostgreSQL (Sprint 40's infrastructure — pg_session,
TEST_DATABASE_URL).

Tests ExamSectionService/ExamModuleService directly (matching this
project's existing integration-test style — see
test_module_execution.py) rather than through FastAPI's DI/HTTP layer,
since RBAC itself (require_roles) is an already-proven, project-wide
mechanism this sprint reuses unchanged rather than re-tests.
"""
import uuid

import pytest

from app.modules.tests.exceptions import (
    DuplicateOrderNumberException,
    ExamModuleNotFoundException,
    ExamSectionNotFoundException,
    InvalidTestReferenceException,
)
from app.modules.tests.models import ExamModule, ExamSection, Test
from app.modules.tests.repository import ExamModuleRepository, ExamSectionRepository, TestRepository
from app.modules.tests.schemas import (
    ExamModuleCreateRequest,
    ExamModuleUpdateRequest,
    ExamSectionCreateRequest,
    ExamSectionUpdateRequest,
)
from app.modules.tests.service import ExamModuleService, ExamSectionService
from app.modules.subjects.models import Subject
from app.modules.users.models import User, UserStatus
from app.modules.roles.models import Role


def _make_admin(pg_session) -> uuid.UUID:
    role = pg_session.query(Role).filter(Role.name == "Admin").one()
    user = User(role_id=role.id, first_name="Ad", last_name="Min", email=f"admin-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    pg_session.flush()
    return user.id


def _make_test(pg_session) -> Test:
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Config Test", duration=60, question_count=0, status="draft")
    pg_session.add(test)
    pg_session.flush()
    return test


def _section_service(pg_session) -> ExamSectionService:
    return ExamSectionService(ExamSectionRepository(pg_session), TestRepository(pg_session))


def _module_service(pg_session) -> ExamModuleService:
    return ExamModuleService(ExamModuleRepository(pg_session), ExamSectionRepository(pg_session))


# --- ExamSection: create, list/get, update, duplicate order, invalid test ---

def test_admin_creates_exam_section(pg_session):
    admin_id = _make_admin(pg_session)
    test = _make_test(pg_session)
    service = _section_service(pg_session)

    section = service.create_section(
        ExamSectionCreateRequest(test_id=test.id, name="Reading and Writing", order_number=0, duration=60), admin_id,
    )
    pg_session.commit()

    reloaded = pg_session.query(ExamSection).filter(ExamSection.id == section.id).one()
    assert reloaded.test_id == test.id
    assert reloaded.name == "Reading and Writing"
    assert reloaded.duration == 60


def test_admin_lists_and_gets_exam_sections(pg_session):
    admin_id = _make_admin(pg_session)
    test = _make_test(pg_session)
    service = _section_service(pg_session)
    service.create_section(ExamSectionCreateRequest(test_id=test.id, name="A", order_number=0), admin_id)
    service.create_section(ExamSectionCreateRequest(test_id=test.id, name="B", order_number=1), admin_id)
    pg_session.commit()

    sections = service.list_sections(test.id)
    assert [s.name for s in sections] == ["A", "B"]

    fetched = service.get_section(sections[0].id)
    assert fetched.name == "A"


def test_admin_updates_exam_section(pg_session):
    admin_id = _make_admin(pg_session)
    test = _make_test(pg_session)
    service = _section_service(pg_session)
    section = service.create_section(ExamSectionCreateRequest(test_id=test.id, name="Original", order_number=0), admin_id)
    pg_session.commit()

    updated = service.update_section(section.id, ExamSectionUpdateRequest(name="Renamed"), admin_id)
    pg_session.commit()

    assert updated.name == "Renamed"


def test_duplicate_section_order_number_rejected(pg_session):
    admin_id = _make_admin(pg_session)
    test = _make_test(pg_session)
    service = _section_service(pg_session)
    service.create_section(ExamSectionCreateRequest(test_id=test.id, name="First", order_number=0), admin_id)
    pg_session.commit()

    with pytest.raises(DuplicateOrderNumberException):
        service.create_section(ExamSectionCreateRequest(test_id=test.id, name="Duplicate", order_number=0), admin_id)


def test_invalid_test_id_rejected_for_section(pg_session):
    admin_id = _make_admin(pg_session)
    service = _section_service(pg_session)

    with pytest.raises(InvalidTestReferenceException):
        service.create_section(ExamSectionCreateRequest(test_id=uuid.uuid4(), name="X", order_number=0), admin_id)


def test_nonexistent_section_returns_not_found(pg_session):
    service = _section_service(pg_session)
    with pytest.raises(ExamSectionNotFoundException):
        service.get_section(uuid.uuid4())


# --- ExamModule: create, list/get, update, duplicate order, invalid section, cross-parent ---

def test_admin_creates_exam_module(pg_session):
    admin_id = _make_admin(pg_session)
    test = _make_test(pg_session)
    section_service = _section_service(pg_session)
    section = section_service.create_section(ExamSectionCreateRequest(test_id=test.id, name="Math", order_number=0), admin_id)
    pg_session.commit()

    module_service = _module_service(pg_session)
    module = module_service.create_module(
        ExamModuleCreateRequest(
            section_id=section.id, name="Module 1", order_number=0, duration=35,
            routing_group="math", routing_variant="module_1",
        ),
        admin_id,
    )
    pg_session.commit()

    reloaded = pg_session.query(ExamModule).filter(ExamModule.id == module.id).one()
    assert reloaded.section_id == section.id
    assert reloaded.routing_group == "math"
    assert reloaded.routing_variant == "module_1"


def test_admin_lists_and_gets_exam_modules(pg_session):
    admin_id = _make_admin(pg_session)
    test = _make_test(pg_session)
    section_service = _section_service(pg_session)
    section = section_service.create_section(ExamSectionCreateRequest(test_id=test.id, name="Math", order_number=0), admin_id)
    pg_session.commit()

    module_service = _module_service(pg_session)
    module_service.create_module(ExamModuleCreateRequest(section_id=section.id, name="M1", order_number=0), admin_id)
    module_service.create_module(ExamModuleCreateRequest(section_id=section.id, name="M2", order_number=1), admin_id)
    pg_session.commit()

    modules = module_service.list_modules(section.id)
    assert [m.name for m in modules] == ["M1", "M2"]

    fetched = module_service.get_module(modules[0].id)
    assert fetched.name == "M1"


def test_admin_updates_exam_module(pg_session):
    admin_id = _make_admin(pg_session)
    test = _make_test(pg_session)
    section_service = _section_service(pg_session)
    section = section_service.create_section(ExamSectionCreateRequest(test_id=test.id, name="Math", order_number=0), admin_id)
    pg_session.commit()

    module_service = _module_service(pg_session)
    module = module_service.create_module(ExamModuleCreateRequest(section_id=section.id, name="Original", order_number=0), admin_id)
    pg_session.commit()

    updated = module_service.update_module(module.id, ExamModuleUpdateRequest(name="Renamed", routing_group="verbal"), admin_id)
    pg_session.commit()

    assert updated.name == "Renamed"
    assert updated.routing_group == "verbal"


def test_duplicate_module_order_number_rejected(pg_session):
    admin_id = _make_admin(pg_session)
    test = _make_test(pg_session)
    section_service = _section_service(pg_session)
    section = section_service.create_section(ExamSectionCreateRequest(test_id=test.id, name="Math", order_number=0), admin_id)
    pg_session.commit()

    module_service = _module_service(pg_session)
    module_service.create_module(ExamModuleCreateRequest(section_id=section.id, name="First", order_number=0), admin_id)
    pg_session.commit()

    with pytest.raises(DuplicateOrderNumberException):
        module_service.create_module(ExamModuleCreateRequest(section_id=section.id, name="Duplicate", order_number=0), admin_id)


def test_invalid_section_id_rejected_for_module(pg_session):
    admin_id = _make_admin(pg_session)
    module_service = _module_service(pg_session)

    with pytest.raises(ExamSectionNotFoundException):
        module_service.create_module(ExamModuleCreateRequest(section_id=uuid.uuid4(), name="X", order_number=0), admin_id)


def test_nonexistent_module_returns_not_found(pg_session):
    module_service = _module_service(pg_session)
    with pytest.raises(ExamModuleNotFoundException):
        module_service.get_module(uuid.uuid4())


def test_two_different_sections_can_each_have_module_order_zero(pg_session):
    """Cross-parent: order_number uniqueness is scoped per-section, not
    global — two modules in DIFFERENT sections may both be order 0."""
    admin_id = _make_admin(pg_session)
    test = _make_test(pg_session)
    section_service = _section_service(pg_session)
    section_a = section_service.create_section(ExamSectionCreateRequest(test_id=test.id, name="A", order_number=0), admin_id)
    section_b = section_service.create_section(ExamSectionCreateRequest(test_id=test.id, name="B", order_number=1), admin_id)
    pg_session.commit()

    module_service = _module_service(pg_session)
    module_service.create_module(ExamModuleCreateRequest(section_id=section_a.id, name="A-M1", order_number=0), admin_id)
    module_service.create_module(ExamModuleCreateRequest(section_id=section_b.id, name="B-M1", order_number=0), admin_id)
    pg_session.commit()  # must not raise
