"""
Sprint 56 — Question Answer-Key Access Control, against real PostgreSQL
(Sprint 40's infrastructure — pg_session, TEST_DATABASE_URL). Real HTTP
requests through TestClient with real JWT tokens (matching the
established RBAC-verification pattern used in Sprint 53's
test_question_group_api.py) — no dependency-function unit test, no
mocked authorization, exercised through the actual router.

Security fix under test: GET /questions and GET /questions/{question_id}
used to accept any authenticated user, even though QuestionOut includes
is_correct on every option (content-authoring view). Any Student could
call these endpoints directly and read the full answer key for any
question, bypassing the entire attempt-flow answer-hiding design. Fixed
by requiring Admin/Super Admin/Teacher, the same roles already required
by every write endpoint in this router.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security.dependencies import get_jwt_service
from app.main import app
from app.modules.questions.models import Question, QuestionOption
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import Test
from app.modules.users.models import User, UserStatus


def _make_user(pg_session, role_name: str) -> User:
    role = pg_session.query(Role).filter(Role.name == role_name).one()
    user = User(
        role_id=role.id, first_name="U", last_name=role_name,
        email=f"{role_name.replace(' ', '')}-{uuid.uuid4()}@example.com",
        password_hash="x", status=UserStatus.ACTIVE,
    )
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
    test = Test(subject_id=subject.id, title=title, duration=30, question_count=1, status="draft")
    pg_session.add(test)
    pg_session.flush()
    return test


def _make_question_with_options(pg_session, test_id) -> Question:
    question = Question(test_id=test_id, question_text="2 + 2 = ?", question_type="single_choice", score=1)
    pg_session.add(question)
    pg_session.flush()
    pg_session.add_all([
        QuestionOption(question_id=question.id, option_text="4", is_correct=True),
        QuestionOption(question_id=question.id, option_text="5", is_correct=False),
    ])
    pg_session.flush()
    return question


# --- A/B: Student is forbidden ---

def test_student_cannot_list_questions(client: TestClient, pg_session):
    student = _make_user(pg_session, "Student")
    test = _make_test(pg_session)
    _make_question_with_options(pg_session, test.id)
    pg_session.commit()

    r = client.get("/api/v1/questions", params={"test_id": str(test.id)}, headers=_auth(student))

    assert r.status_code == 403, r.text


def test_student_cannot_retrieve_single_question(client: TestClient, pg_session):
    student = _make_user(pg_session, "Student")
    test = _make_test(pg_session)
    question = _make_question_with_options(pg_session, test.id)
    pg_session.commit()

    r = client.get(f"/api/v1/questions/{question.id}", headers=_auth(student))

    assert r.status_code == 403, r.text
    # Security-critical: the answer key must not leak in the body either,
    # not just via the status code.
    assert "is_correct" not in r.text


# --- C/D: Admin is allowed, is_correct still present ---

def test_admin_can_list_questions_with_answer_key(client: TestClient, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    _make_question_with_options(pg_session, test.id)
    pg_session.commit()

    r = client.get("/api/v1/questions", params={"test_id": str(test.id)}, headers=_auth(admin))

    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert len(items) == 1
    options = items[0]["options"]
    assert any(o["is_correct"] is True for o in options)
    assert any(o["is_correct"] is False for o in options)


def test_admin_can_retrieve_single_question_with_answer_key(client: TestClient, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    question = _make_question_with_options(pg_session, test.id)
    pg_session.commit()

    r = client.get(f"/api/v1/questions/{question.id}", headers=_auth(admin))

    assert r.status_code == 200, r.text
    options = r.json()["data"]["options"]
    assert any(o["is_correct"] is True for o in options)


# --- E/F: Super Admin and Teacher are allowed ---

@pytest.mark.parametrize("role_name", ["Super Admin", "Teacher"])
def test_super_admin_and_teacher_can_list_and_retrieve(client: TestClient, pg_session, role_name):
    user = _make_user(pg_session, role_name)
    test = _make_test(pg_session)
    question = _make_question_with_options(pg_session, test.id)
    pg_session.commit()

    list_response = client.get("/api/v1/questions", params={"test_id": str(test.id)}, headers=_auth(user))
    detail_response = client.get(f"/api/v1/questions/{question.id}", headers=_auth(user))

    assert list_response.status_code == 200, list_response.text
    assert detail_response.status_code == 200, detail_response.text


# --- G: unauthenticated stays 401 ---

def test_unauthenticated_cannot_list_questions(client: TestClient, pg_session):
    test = _make_test(pg_session)
    _make_question_with_options(pg_session, test.id)
    pg_session.commit()

    r = client.get("/api/v1/questions", params={"test_id": str(test.id)})

    assert r.status_code == 401, r.text


def test_unauthenticated_cannot_retrieve_single_question(client: TestClient, pg_session):
    test = _make_test(pg_session)
    question = _make_question_with_options(pg_session, test.id)
    pg_session.commit()

    r = client.get(f"/api/v1/questions/{question.id}")

    assert r.status_code == 401, r.text
