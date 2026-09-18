"""
Sprint 53 — QuestionGroup / Stimulus Admin CRUD API integration tests,
against real PostgreSQL (Sprint 40's infrastructure — pg_session,
TEST_DATABASE_URL). Uses real HTTP requests through TestClient (per
this sprint's explicit requirement) with real JWT tokens, matching the
established pattern for RBAC/route-collision verification (see the
Sprint 51 final audit's own RBAC testing approach).
"""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security.dependencies import get_jwt_service
from app.main import app
from app.modules.questions.models import Question
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import ExamModule, ExamSection, QuestionGroup, Test
from app.modules.users.models import User, UserStatus


def _make_user(pg_session, role_name: str) -> User:
    role = pg_session.query(Role).filter(Role.name == role_name).one()
    user = User(role_id=role.id, first_name="U", last_name=role_name, email=f"{role_name}-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    pg_session.flush()
    return user


def _token(user: User) -> str:
    return get_jwt_service().create_access_token(str(user.id))


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {_token(user)}"}


def _make_test(pg_session, title="T") -> Test:
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title=title, duration=30, question_count=0, status="draft")
    pg_session.add(test)
    pg_session.flush()
    return test


# --- A/B: successful creation (test-scoped and module-scoped) ---

def test_admin_creates_test_scoped_group(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()

    r = client.post("/api/v1/tests/question-groups", json={
        "test_id": str(test.id), "title": "Passage 1", "stimulus_text": "Once upon a time...", "order_number": 0,
    }, headers=_auth(admin))

    assert r.status_code == 201, r.text
    body = r.json()["data"]
    assert body["test_id"] == str(test.id)
    assert body["title"] == "Passage 1"
    assert body["module_id"] is None


def test_admin_creates_module_scoped_group(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module = ExamModule(section_id=section.id, name="Module", order_number=0)
    pg_session.add(module)
    pg_session.commit()

    r = client.post("/api/v1/tests/question-groups", json={
        "test_id": str(test.id), "module_id": str(module.id), "title": "Audio 1", "order_number": 0,
    }, headers=_auth(admin))

    assert r.status_code == 201, r.text
    assert r.json()["data"]["module_id"] == str(module.id)


# --- C/D/E: rejection cases ---

def test_nonexistent_test_rejected(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    pg_session.commit()

    r = client.post("/api/v1/tests/question-groups", json={
        "test_id": str(uuid.uuid4()), "title": "X", "order_number": 0,
    }, headers=_auth(admin))

    assert r.status_code in (404, 422), r.text


def test_nonexistent_module_rejected(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()

    r = client.post("/api/v1/tests/question-groups", json={
        "test_id": str(test.id), "module_id": str(uuid.uuid4()), "title": "X", "order_number": 0,
    }, headers=_auth(admin))

    assert r.status_code in (404, 422), r.text


def test_module_from_another_test_rejected(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test_a = _make_test(pg_session, "A")
    test_b = _make_test(pg_session, "B")
    section_b = ExamSection(test_id=test_b.id, name="Section B", order_number=0)
    pg_session.add(section_b)
    pg_session.flush()
    module_b = ExamModule(section_id=section_b.id, name="Module B", order_number=0)
    pg_session.add(module_b)
    pg_session.commit()

    r = client.post("/api/v1/tests/question-groups", json={
        "test_id": str(test_a.id), "module_id": str(module_b.id), "title": "X", "order_number": 0,
    }, headers=_auth(admin))

    assert r.status_code in (404, 422), r.text


# --- F/G: order_number uniqueness ---

def test_duplicate_order_number_same_test_rejected(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()

    r1 = client.post("/api/v1/tests/question-groups", json={"test_id": str(test.id), "title": "First", "order_number": 0}, headers=_auth(admin))
    assert r1.status_code == 201, r1.text

    r2 = client.post("/api/v1/tests/question-groups", json={"test_id": str(test.id), "title": "Duplicate", "order_number": 0}, headers=_auth(admin))
    assert r2.status_code == 409, r2.text


def test_same_order_number_different_tests_allowed(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test_a = _make_test(pg_session, "A")
    test_b = _make_test(pg_session, "B")
    pg_session.commit()

    r1 = client.post("/api/v1/tests/question-groups", json={"test_id": str(test_a.id), "title": "A-Group", "order_number": 0}, headers=_auth(admin))
    r2 = client.post("/api/v1/tests/question-groups", json={"test_id": str(test_b.id), "title": "B-Group", "order_number": 0}, headers=_auth(admin))

    assert r1.status_code == 201, r1.text
    assert r2.status_code == 201, r2.text


# --- H/I: GET list/single ---

def test_get_list_by_test(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()
    client.post("/api/v1/tests/question-groups", json={"test_id": str(test.id), "title": "A", "order_number": 0}, headers=_auth(admin))
    client.post("/api/v1/tests/question-groups", json={"test_id": str(test.id), "title": "B", "order_number": 1}, headers=_auth(admin))

    r = client.get(f"/api/v1/tests/question-groups?test_id={test.id}", headers=_auth(admin))

    assert r.status_code == 200, r.text
    titles = [g["title"] for g in r.json()["data"]]
    assert titles == ["A", "B"]


def test_get_single_group(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()
    created = client.post("/api/v1/tests/question-groups", json={"test_id": str(test.id), "title": "Solo", "order_number": 0}, headers=_auth(admin)).json()["data"]

    r = client.get(f"/api/v1/tests/question-groups/{created['id']}", headers=_auth(admin))

    assert r.status_code == 200, r.text
    assert r.json()["data"]["title"] == "Solo"


# --- J/K/L/M/N: PATCH semantics ---

def test_patch_title(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()
    created = client.post("/api/v1/tests/question-groups", json={"test_id": str(test.id), "title": "Original", "order_number": 0}, headers=_auth(admin)).json()["data"]

    r = client.patch(f"/api/v1/tests/question-groups/{created['id']}", json={"title": "Renamed"}, headers=_auth(admin))

    assert r.status_code == 200, r.text
    assert r.json()["data"]["title"] == "Renamed"


def test_patch_stimulus_text(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()
    created = client.post("/api/v1/tests/question-groups", json={"test_id": str(test.id), "title": "G", "order_number": 0}, headers=_auth(admin)).json()["data"]

    r = client.patch(f"/api/v1/tests/question-groups/{created['id']}", json={"stimulus_text": "Updated passage text."}, headers=_auth(admin))

    assert r.status_code == 200, r.text
    assert r.json()["data"]["stimulus_text"] == "Updated passage text."


def test_patch_module_id(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module = ExamModule(section_id=section.id, name="Module", order_number=0)
    pg_session.add(module)
    pg_session.commit()
    created = client.post("/api/v1/tests/question-groups", json={"test_id": str(test.id), "title": "G", "order_number": 0}, headers=_auth(admin)).json()["data"]

    r = client.patch(f"/api/v1/tests/question-groups/{created['id']}", json={"module_id": str(module.id)}, headers=_auth(admin))

    assert r.status_code == 200, r.text
    assert r.json()["data"]["module_id"] == str(module.id)


def test_patch_explicit_null_module_id_unassigns(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module = ExamModule(section_id=section.id, name="Module", order_number=0)
    pg_session.add(module)
    pg_session.commit()
    created = client.post("/api/v1/tests/question-groups", json={
        "test_id": str(test.id), "module_id": str(module.id), "title": "G", "order_number": 0,
    }, headers=_auth(admin)).json()["data"]

    r = client.patch(f"/api/v1/tests/question-groups/{created['id']}", json={"module_id": None}, headers=_auth(admin))

    assert r.status_code == 200, r.text
    assert r.json()["data"]["module_id"] is None


def test_patch_omitted_fields_preserve_values(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()
    created = client.post("/api/v1/tests/question-groups", json={
        "test_id": str(test.id), "title": "Original", "stimulus_text": "Keep me", "order_number": 0,
    }, headers=_auth(admin)).json()["data"]

    r = client.patch(f"/api/v1/tests/question-groups/{created['id']}", json={"title": "Only title changed"}, headers=_auth(admin))

    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["title"] == "Only title changed"
    assert body["stimulus_text"] == "Keep me"  # unchanged, not wiped


# --- O/P: PATCH order_number validation ---

def test_patch_duplicate_order_number_rejected(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()
    client.post("/api/v1/tests/question-groups", json={"test_id": str(test.id), "title": "A", "order_number": 0}, headers=_auth(admin))
    second = client.post("/api/v1/tests/question-groups", json={"test_id": str(test.id), "title": "B", "order_number": 1}, headers=_auth(admin)).json()["data"]

    r = client.patch(f"/api/v1/tests/question-groups/{second['id']}", json={"order_number": 0}, headers=_auth(admin))

    assert r.status_code == 409, r.text


def test_patch_same_order_number_succeeds(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()
    created = client.post("/api/v1/tests/question-groups", json={"test_id": str(test.id), "title": "A", "order_number": 0}, headers=_auth(admin)).json()["data"]

    r = client.patch(f"/api/v1/tests/question-groups/{created['id']}", json={"order_number": 0, "title": "Renamed"}, headers=_auth(admin))

    assert r.status_code == 200, r.text


# --- Q/R/S: DELETE (soft) behavior ---

def test_delete_performs_soft_delete(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()
    created = client.post("/api/v1/tests/question-groups", json={"test_id": str(test.id), "title": "ToDelete", "order_number": 0}, headers=_auth(admin)).json()["data"]

    r = client.delete(f"/api/v1/tests/question-groups/{created['id']}", headers=_auth(admin))
    assert r.status_code == 204, r.text

    pg_session.expire_all()
    row = pg_session.get(QuestionGroup, uuid.UUID(created["id"]))
    assert row is not None
    assert row.deleted_at is not None


def test_deleted_group_not_returned_by_list(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()
    created = client.post("/api/v1/tests/question-groups", json={"test_id": str(test.id), "title": "ToDelete", "order_number": 0}, headers=_auth(admin)).json()["data"]
    client.delete(f"/api/v1/tests/question-groups/{created['id']}", headers=_auth(admin))

    r = client.get(f"/api/v1/tests/question-groups?test_id={test.id}", headers=_auth(admin))
    assert r.status_code == 200, r.text
    assert r.json()["data"] == []

    r_single = client.get(f"/api/v1/tests/question-groups/{created['id']}", headers=_auth(admin))
    assert r_single.status_code == 404


def test_existing_question_remains_after_group_deletion(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()
    created = client.post("/api/v1/tests/question-groups", json={"test_id": str(test.id), "title": "G", "order_number": 0}, headers=_auth(admin)).json()["data"]
    group_id = uuid.UUID(created["id"])

    question = Question(test_id=test.id, question_text="Q", question_type="single_choice", score=1, group_id=group_id)
    pg_session.add(question)
    pg_session.commit()

    r = client.delete(f"/api/v1/tests/question-groups/{group_id}", headers=_auth(admin))
    assert r.status_code == 204, r.text

    pg_session.expire_all()
    reloaded_question = pg_session.get(Question, question.id)
    assert reloaded_question is not None
    # Soft delete does NOT trigger the ON DELETE SET NULL FK (that only
    # fires on a real hard DELETE, which this endpoint deliberately
    # does not perform) — group_id correctly still points at the
    # (now soft-deleted) group. What matters, and what Sprint 53
    # actually requires, is that the Question itself is completely
    # untouched: not deleted, not modified.
    assert reloaded_question.group_id == group_id
    assert reloaded_question.deleted_at is None  # the question itself is untouched
    assert reloaded_question.question_text == "Q"  # unchanged


# --- T/U/V: RBAC ---

def test_teacher_forbidden(client, pg_session):
    teacher = _make_user(pg_session, "Teacher")
    test = _make_test(pg_session)
    pg_session.commit()

    r = client.post("/api/v1/tests/question-groups", json={"test_id": str(test.id), "title": "X", "order_number": 0}, headers=_auth(teacher))
    assert r.status_code == 403


def test_student_forbidden(client, pg_session):
    student = _make_user(pg_session, "Student")
    test = _make_test(pg_session)
    pg_session.commit()

    r = client.post("/api/v1/tests/question-groups", json={"test_id": str(test.id), "title": "X", "order_number": 0}, headers=_auth(student))
    assert r.status_code == 403


def test_unauthenticated_forbidden(client, pg_session):
    test = _make_test(pg_session)
    pg_session.commit()

    r = client.post("/api/v1/tests/question-groups", json={"test_id": str(test.id), "title": "X", "order_number": 0})
    assert r.status_code == 401


# --- W/X: cross-test IDOR ---

def test_cross_test_idor_via_patch_rejected(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test_a = _make_test(pg_session, "A")
    test_b = _make_test(pg_session, "B")
    pg_session.commit()
    group_a = client.post("/api/v1/tests/question-groups", json={"test_id": str(test_a.id), "title": "GA", "order_number": 0}, headers=_auth(admin)).json()["data"]
    section_b = ExamSection(test_id=test_b.id, name="Section B", order_number=0)
    pg_session.add(section_b)
    pg_session.flush()
    module_b = ExamModule(section_id=section_b.id, name="Module B", order_number=0)
    pg_session.add(module_b)
    pg_session.commit()

    r = client.patch(f"/api/v1/tests/question-groups/{group_a['id']}", json={"module_id": str(module_b.id)}, headers=_auth(admin))

    assert r.status_code in (404, 422), r.text


# --- Y: route collision regression ---

def test_route_collision_regression(client, pg_session):
    """GET /tests/question-groups?test_id=... must reach the
    QuestionGroup handler, not the dynamic /tests/{test_id} route."""
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()

    r = client.get(f"/api/v1/tests/question-groups?test_id={test.id}", headers=_auth(admin))

    assert r.status_code == 200, r.text
    assert isinstance(r.json()["data"], list)
