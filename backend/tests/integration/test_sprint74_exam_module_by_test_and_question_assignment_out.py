"""
Sprint 74 — Admin Exam Configuration UI backend support. Two additive,
non-migration changes, tested here against real HTTP requests through
TestClient (same established pattern as test_question_group_api.py):

1. GET /tests/exam-modules now accepts test_id as an alternative to
   section_id (every module across a whole test in one call, avoiding
   one request per section). Exactly one of the two must be given.
2. QuestionOut now includes section_id/module_id/group_id — the
   question's current exam-structure assignment, previously invisible
   on the read side despite being settable via PATCH.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security.dependencies import get_jwt_service
from app.main import app
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import Test
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


# --- GET /tests/exam-modules?test_id=... ---

def test_admin_lists_exam_modules_by_test_id(client: TestClient, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()

    r_section_a = client.post("/api/v1/tests/exam-sections", json={"test_id": str(test.id), "name": "A", "order_number": 0}, headers=_auth(admin))
    r_section_b = client.post("/api/v1/tests/exam-sections", json={"test_id": str(test.id), "name": "B", "order_number": 1}, headers=_auth(admin))
    section_a_id = r_section_a.json()["data"]["id"]
    section_b_id = r_section_b.json()["data"]["id"]

    client.post("/api/v1/tests/exam-modules", json={"section_id": section_b_id, "name": "B1", "order_number": 0}, headers=_auth(admin))
    client.post("/api/v1/tests/exam-modules", json={"section_id": section_a_id, "name": "A1", "order_number": 0}, headers=_auth(admin))

    r = client.get("/api/v1/tests/exam-modules", params={"test_id": str(test.id)}, headers=_auth(admin))
    assert r.status_code == 200, r.text
    names = [m["name"] for m in r.json()["data"]]
    assert names == ["A1", "B1"]


def test_exam_modules_requires_exactly_one_of_section_id_or_test_id(client: TestClient, pg_session):
    admin = _make_user(pg_session, "Admin")
    pg_session.commit()

    r_neither = client.get("/api/v1/tests/exam-modules", headers=_auth(admin))
    assert r_neither.status_code == 422, r_neither.text

    test = _make_test(pg_session)
    section = client.post("/api/v1/tests/exam-sections", json={"test_id": str(test.id), "name": "A", "order_number": 0}, headers=_auth(admin)).json()["data"]
    r_both = client.get(
        "/api/v1/tests/exam-modules",
        params={"section_id": section["id"], "test_id": str(test.id)},
        headers=_auth(admin),
    )
    assert r_both.status_code == 422, r_both.text


def test_exam_modules_by_test_id_rejects_nonexistent_test(client: TestClient, pg_session):
    admin = _make_user(pg_session, "Admin")
    pg_session.commit()

    r = client.get("/api/v1/tests/exam-modules", params={"test_id": str(uuid.uuid4())}, headers=_auth(admin))
    assert r.status_code == 422, r.text


# --- QuestionOut.section_id/module_id/group_id ---

def test_question_out_exposes_current_assignment(client: TestClient, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()

    section = client.post("/api/v1/tests/exam-sections", json={"test_id": str(test.id), "name": "A", "order_number": 0}, headers=_auth(admin)).json()["data"]

    r_create = client.post("/api/v1/questions", json={"test_id": str(test.id), "question_text": "Q1?", "question_type": "essay"}, headers=_auth(admin))
    assert r_create.status_code == 201, r_create.text
    question_id = r_create.json()["data"]["id"]
    # Never assigned yet — must be explicitly null, not just absent.
    assert r_create.json()["data"]["section_id"] is None

    r_patch = client.patch(f"/api/v1/questions/{question_id}", json={"section_id": section["id"]}, headers=_auth(admin))
    assert r_patch.status_code == 200, r_patch.text
    assert r_patch.json()["data"]["section_id"] == section["id"]
    assert r_patch.json()["data"]["module_id"] is None
    assert r_patch.json()["data"]["group_id"] is None

    r_get = client.get(f"/api/v1/questions/{question_id}", headers=_auth(admin))
    assert r_get.json()["data"]["section_id"] == section["id"]
