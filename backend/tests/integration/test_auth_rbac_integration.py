"""
Sprint 40 Phase 3 — Integration Test 4: Authentication/RBAC through the
real FastAPI client (dependency_overrides -> pg_session), real
PostgreSQL, real JWT, real password hashing (Argon2, via the existing
PasswordService/seed_super_admin — no parallel auth implementation).
"""
import uuid

from app.core.security.password_service import PasswordService
from app.modules.roles.models import Role
from app.modules.users.models import User, UserStatus
from scripts.seed_admin import seed_super_admin


def _create_super_admin(pg_session) -> tuple[str, str]:
    """Uses the EXISTING seed mechanism (Sprint 39's seed_super_admin),
    not a parallel/duplicate auth setup."""
    email = f"admin-{uuid.uuid4()}@example.com"
    password = "Integration-T3st-P@ss1"
    success, message = seed_super_admin(pg_session, email, password, "Integration", "Admin")
    assert success, message
    return email, password


def _create_student(pg_session) -> tuple[str, str]:
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    email = f"student-{uuid.uuid4()}@example.com"
    password = "Integration-T3st-P@ss2"
    user = User(
        role_id=role.id, first_name="Integration", last_name="Student",
        email=email, password_hash=PasswordService().hash_password(password), status=UserStatus.ACTIVE,
    )
    pg_session.add(user)
    pg_session.flush()
    return email, password


def test_super_admin_login_returns_real_jwt_tokens(client, pg_session):
    email, password = _create_super_admin(pg_session)

    response = client.post("/api/v1/auth/login", json={"identifier": email, "password": password})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "access_token" in body["data"]
    assert "refresh_token" in body["data"]
    assert body["data"]["token_type"] == "bearer"


def test_super_admin_can_access_protected_endpoint_with_real_token(client, pg_session):
    email, password = _create_super_admin(pg_session)
    login = client.post("/api/v1/auth/login", json={"identifier": email, "password": password})
    token = login.json()["data"]["access_token"]

    response = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_unauthenticated_request_is_rejected(client, pg_session):
    """No Authorization header at all — must not be treated as authorized."""
    response = client.get("/api/v1/users")
    assert response.status_code in (401, 403)


def test_student_role_is_rejected_from_super_admin_only_endpoint(client, pg_session):
    """RBAC negative case: a real, valid JWT for a Student — not a
    missing/invalid token — must still be rejected by an
    Admin/Super-Admin-only endpoint (GET /users requires
    require_roles("Admin", "Super Admin"))."""
    email, password = _create_student(pg_session)
    login = client.post("/api/v1/auth/login", json={"identifier": email, "password": password})
    assert login.status_code == 200  # the login itself succeeds — this IS a real, valid user
    token = login.json()["data"]["access_token"]

    response = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_wrong_password_is_rejected(client, pg_session):
    email, _password = _create_super_admin(pg_session)

    response = client.post("/api/v1/auth/login", json={"identifier": email, "password": "definitely-wrong-password"})

    assert response.status_code in (400, 401)
