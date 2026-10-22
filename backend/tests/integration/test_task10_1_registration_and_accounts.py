"""
Task 10.1 — public self-registration disabled, no OTP disclosure, unverified
accounts locked out, administrator-managed account creation (POST /users).
Real PostgreSQL/Redis and HTTP API.
"""
import uuid

import pytest

from app.core.config import get_settings
from app.core.security.password_service import PasswordService
from app.main import app
from app.modules.auth.models import VerificationCode
from app.modules.roles.models import Role
from app.modules.users.models import User, UserStatus

PASSWORD = "Integration-T3st-P@ss1"
API = "/api/v1"


def _user(db, role="Student", status=UserStatus.ACTIVE) -> User:
    r = db.query(Role).filter(Role.name == role).one()
    u = User(role_id=r.id, first_name="Reg", last_name=role, email=f"reg-{uuid.uuid4()}@example.com",
             password_hash=PasswordService().hash_password(PASSWORD), status=status)
    db.add(u)
    db.commit()
    return u


def _token(client, user) -> dict:
    r = client.post(f"{API}/auth/login", json={"identifier": user.email, "password": PASSWORD})
    assert r.status_code == 200, r.json()
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


def _phone() -> str:
    return "+99890" + str(uuid.uuid4().int)[:7]


def _register_body(phone=None):
    return {"first_name": "Ali", "last_name": "Valiyev", "phone": phone or _phone(), "password": PASSWORD}


@pytest.fixture
def registration_enabled():
    enabled = get_settings().model_copy(update={"PUBLIC_REGISTRATION_ENABLED": True})
    app.dependency_overrides[get_settings] = lambda: enabled
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_settings, None)


# --- public registration ----------------------------------------------------------------

def test_registration_is_disabled_by_default(client, pg_session):
    assert get_settings().PUBLIC_REGISTRATION_ENABLED is False
    body = _register_body()
    r = client.post(f"{API}/auth/register", json=body)
    assert r.status_code == 403
    assert "administrator" in r.json()["message"]
    assert pg_session.query(User).filter(User.phone == body["phone"]).count() == 0


def test_enabled_registration_never_discloses_the_code(client, pg_session, registration_enabled, monkeypatch):
    monkeypatch.setattr("app.modules.auth.service.generate_verification_code", lambda: "482913")
    body = _register_body()
    r = client.post(f"{API}/auth/register", json=body)
    assert r.status_code == 201, r.json()
    assert set(r.json()["data"]) == {"user_id"}
    assert "482913" not in r.text and "debug_code" not in r.text
    user = pg_session.query(User).filter(User.phone == body["phone"]).one()
    assert user.status == UserStatus.PENDING_VERIFICATION
    # Only a hash is stored.
    row = pg_session.query(VerificationCode).filter(VerificationCode.user_id == user.id).one()
    assert "482913" not in row.code_hash

    # Unverified: no login.
    denied = client.post(f"{API}/auth/login", json={"identifier": body["phone"], "password": PASSWORD})
    assert denied.status_code == 403 and "tasdiqlanmagan" in denied.json()["message"]
    assert client.cookies.get("refresh_token") is None

    # With the out-of-band code the account becomes active and can log in.
    assert client.post(f"{API}/auth/verify", json={"user_id": str(user.id), "code": "000000"}).status_code == 400
    ok = client.post(f"{API}/auth/verify", json={"user_id": str(user.id), "code": "482913"})
    assert ok.status_code == 200 and "482913" not in ok.text
    assert client.post(f"{API}/auth/login", json={"identifier": body["phone"], "password": PASSWORD}).status_code == 200


def test_pending_account_cannot_use_or_refresh_existing_tokens(client, pg_session):
    user = _user(pg_session)
    headers = _token(client, user)
    pg_session.expire_all()
    pg_session.get(User, user.id).status = UserStatus.PENDING_VERIFICATION
    pg_session.commit()
    me = client.get(f"{API}/auth/me", headers=headers)
    assert me.status_code == 403 and me.json()["message"] == "Akkaunt hali tasdiqlanmagan"
    assert client.post(f"{API}/auth/refresh", headers={"X-CSRF-Token": client.cookies.get("csrf_token")}).status_code == 403


def test_openapi_and_responses_contain_no_otp_field(client):
    spec = client.get(f"{API}/openapi.json").text
    assert "debug_code" not in spec


# --- administrator-managed accounts ------------------------------------------------------

def _create(client, headers, **over):
    body = {"first_name": "Nodira", "last_name": "Karimova", "phone": _phone(), "email": f"new-{uuid.uuid4()}@example.com",
            "password": PASSWORD, "role": "Student", **over}
    return client.post(f"{API}/users", json=body, headers=headers), body


def test_admin_creates_an_active_account_that_can_log_in(client, pg_session):
    admin = _user(pg_session, "Admin")
    r, body = _create(client, _token(client, admin))
    assert r.status_code == 201, r.json()
    data = r.json()["data"]
    assert data["status"] == "active" and "password" not in r.text and "password_hash" not in r.text
    created = pg_session.get(User, uuid.UUID(data["id"]))
    assert created.role.name == "Student" and created.created_by == admin.id
    assert created.password_hash != PASSWORD
    login = client.post(f"{API}/auth/login", json={"identifier": body["phone"], "password": PASSWORD})
    assert login.status_code == 200


@pytest.mark.parametrize("actor, role, expected", [
    ("Admin", "Teacher", 201), ("Admin", "Admin", 403), ("Admin", "Super Admin", 403),
    ("Super Admin", "Admin", 201), ("Super Admin", "Super Admin", 403), ("Super Admin", "Nonexistent", 403),
])
def test_assignable_roles(client, pg_session, actor, role, expected):
    r, _ = _create(client, _token(client, _user(pg_session, actor)), role=role)
    assert r.status_code == expected, r.json()


@pytest.mark.parametrize("role", ["Teacher", "Student"])
def test_only_administrators_can_create_users(client, pg_session, role):
    r, body = _create(client, _token(client, _user(pg_session, role)))
    assert r.status_code == 403
    assert pg_session.query(User).filter(User.phone == body["phone"]).count() == 0


def test_anonymous_cannot_create_users(client):
    r, _ = _create(client, {})
    assert r.status_code == 401


def test_create_user_validation(client, pg_session):
    headers = _token(client, _user(pg_session, "Admin"))
    first, body = _create(client, headers)
    assert first.status_code == 201
    assert _create(client, headers, phone=body["phone"])[0].status_code == 409            # duplicate phone
    assert _create(client, headers, email=body["email"])[0].status_code == 409            # duplicate email
    assert _create(client, headers, password="short")[0].status_code == 422
    assert _create(client, headers, phone="12345")[0].status_code == 422
    assert _create(client, headers, status="banned")[0].status_code == 422                 # unknown field
    assert _create(client, headers, role_id=str(uuid.uuid4()))[0].status_code == 422
