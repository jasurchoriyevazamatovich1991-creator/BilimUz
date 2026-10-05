"""
Sprint 73 — SEC-2. Real FastAPI client (dependency_overrides -> pg_session),
real Redis-backed rate_limit() dependency (same one already proven on
login/register/verify), real PostgreSQL. Confirms the three previously
unprotected endpoints (/auth/refresh, /auth/change-password,
/certificates/verify/{code}) now return 429 once their limit is exceeded.

Each test uses the `client` fixture's own randomly-assigned IP (see
conftest.py's _RealClientIPASGIWrapper) so these tests never share a
rate-limit budget with each other or with any other test file — no
manual Redis flush needed.
"""
import uuid

from app.core.security.password_service import PasswordService
from app.modules.roles.models import Role
from app.modules.users.models import User, UserStatus
from scripts.seed_admin import seed_super_admin


def _create_student(pg_session) -> tuple[str, str]:
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    email = f"student-{uuid.uuid4()}@example.com"
    password = "Integration-T3st-P@ss2"
    user = User(
        role_id=role.id, first_name="Rate", last_name="Limit",
        email=email, password_hash=PasswordService().hash_password(password), status=UserStatus.ACTIVE,
    )
    pg_session.add(user)
    pg_session.flush()
    return email, password


def test_refresh_endpoint_returns_429_after_exceeding_rate_limit(client):
    from app.modules.auth.constants import REFRESH_RATE_LIMIT
    max_requests, _ = REFRESH_RATE_LIMIT

    for _ in range(max_requests):
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
        assert response.status_code != 429

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert response.status_code == 429


def test_change_password_endpoint_returns_429_after_exceeding_rate_limit(client, pg_session):
    from app.modules.auth.constants import CHANGE_PASSWORD_RATE_LIMIT
    max_requests, _ = CHANGE_PASSWORD_RATE_LIMIT

    email, password = _create_student(pg_session)
    login = client.post("/api/v1/auth/login", json={"identifier": email, "password": password})
    assert login.status_code == 200
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    body = {"current_password": "wrong-current-password", "new_password": "A-Valid-New-Pass123"}

    for _ in range(max_requests):
        response = client.post("/api/v1/auth/change-password", json=body, headers=headers)
        assert response.status_code != 429

    response = client.post("/api/v1/auth/change-password", json=body, headers=headers)
    assert response.status_code == 429


def test_certificate_verify_endpoint_returns_429_after_exceeding_rate_limit(client):
    from app.modules.certificates.router import CERTIFICATE_VERIFY_RATE_LIMIT
    max_requests, _ = CERTIFICATE_VERIFY_RATE_LIMIT

    for _ in range(max_requests):
        response = client.get("/api/v1/certificates/verify/NOT-A-REAL-CODE")
        assert response.status_code != 429

    response = client.get("/api/v1/certificates/verify/NOT-A-REAL-CODE")
    assert response.status_code == 429


def test_certificate_verify_still_returns_404_for_unknown_code_when_under_limit(client):
    """Regression guard: the new rate_limit dependency must not change
    the endpoint's existing behavior for a normal, infrequent caller."""
    response = client.get("/api/v1/certificates/verify/DEFINITELY-UNKNOWN-CODE")
    assert response.status_code == 404
