"""
Task 10 — security audit regressions against real PostgreSQL/Redis and the
real HTTP API.

1. Deactivated ('inactive') and banned accounts kept full access: login,
   token refresh and already-issued access tokens all still worked.
2. CORS preflight rejected PUT, breaking the Task 4–6 PUT endpoints for a
   cross-origin browser (local dev frontend :5173 -> backend :8000).
3. Speaking audio was accepted on the client-declared Content-Type alone.
"""
import uuid

import pytest

from app.core.config import get_settings
from app.core.security.password_service import PasswordService
from app.modules.roles.models import Role
from app.modules.users.models import User, UserStatus
from tests.integration.audio_fixtures import audio_bytes
from tests.integration.test_task6_exam_ui import Ctx as ExamCtx, WEBM, _state

PASSWORD = "Integration-T3st-P@ss1"
API = "/api/v1"


def _user(db, role="Student", status=UserStatus.ACTIVE) -> User:
    r = db.query(Role).filter(Role.name == role).one()
    u = User(role_id=r.id, first_name="Sec", last_name=role, email=f"sec-{uuid.uuid4()}@example.com",
             password_hash=PasswordService().hash_password(PASSWORD), status=status)
    db.add(u)
    db.commit()
    return u


def _login(client, user):
    return client.post(f"{API}/auth/login", json={"identifier": user.email, "password": PASSWORD})


def _csrf(client) -> dict:
    return {"X-CSRF-Token": client.cookies.get("csrf_token")}


# --- 1. account status -------------------------------------------------------------------

@pytest.mark.parametrize("status", [UserStatus.INACTIVE, UserStatus.BANNED])
def test_disabled_accounts_cannot_log_in(client, pg_session, status):
    user = _user(pg_session, status=status)
    r = _login(client, user)
    assert r.status_code == 403
    assert (r.json()["success"], r.json()["data"]) == (False, None)
    assert "faol emas" in r.json()["message"]
    assert client.cookies.get("refresh_token") is None
    # A wrong password still gets the generic 401 (status is not disclosed).
    bad = client.post(f"{API}/auth/login", json={"identifier": user.email, "password": "Wrong-Pass-123!"})
    assert bad.status_code == 401


def test_deactivation_revokes_access_and_refresh_immediately(client, pg_session):
    user = _user(pg_session)
    r = _login(client, user)
    assert r.status_code == 200
    access = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}
    assert client.get(f"{API}/auth/me", headers=access).status_code == 200

    # An administrator deactivates the account through the real API.
    admin = _user(pg_session, "Admin")
    admin_client_headers = {"Authorization": f"Bearer {_login(client, admin).json()['data']['access_token']}"}
    # Logging the admin in replaced the shared cookie jar, so log the student
    # in again to hold their refresh cookie, then deactivate.
    student_tokens = _login(client, user).json()["data"]
    access = {"Authorization": f"Bearer {student_tokens['access_token']}"}
    patched = client.patch(f"{API}/users/{user.id}", json={"status": "inactive"}, headers=admin_client_headers)
    assert patched.status_code == 200, patched.json()

    me = client.get(f"{API}/auth/me", headers=access)                       # still-valid access token
    assert me.status_code == 403
    assert (me.json()["data"], me.json()["message"]) == (None, "Akkaunt faol emas")
    refreshed = client.post(f"{API}/auth/refresh", headers=_csrf(client))  # still-valid refresh cookie
    assert refreshed.status_code == 403
    # The refresh token was consumed, so it cannot be replayed after reactivation either.
    pg_session.expire_all()
    pg_session.get(User, user.id).status = UserStatus.ACTIVE
    pg_session.commit()
    assert client.post(f"{API}/auth/refresh", headers=_csrf(client)).status_code == 401
    assert client.get(f"{API}/auth/me", headers=access).status_code == 200     # reactivated account works again


def test_pending_verification_accounts_cannot_log_in(client, pg_session):
    """Task 10.1 — changed from Task 10: an unverified ('pending_verification')
    account is now refused too (see test_task10_1_registration_and_accounts.py)."""
    user = _user(pg_session, status=UserStatus.PENDING_VERIFICATION)
    r = _login(client, user)
    assert r.status_code == 403 and "tasdiqlanmagan" in r.json()["message"]


# --- 2. CORS ----------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/tests/00000000-0000-0000-0000-000000000000/scoring-profile",
                                  "/grading/submissions/00000000-0000-0000-0000-000000000000/00000000-0000-0000-0000-000000000000/draft",
                                  "/attempts/00000000-0000-0000-0000-000000000000/review-marks/00000000-0000-0000-0000-000000000000"])
def test_cors_preflight_allows_put_from_the_configured_origin(client, path):
    origin = get_settings().ALLOWED_ORIGINS[0]
    r = client.options(f"{API}{path}", headers={"Origin": origin, "Access-Control-Request-Method": "PUT",
                                                 "Access-Control-Request-Headers": "authorization,content-type"})
    assert r.status_code == 200
    assert "PUT" in r.headers["access-control-allow-methods"]
    assert r.headers["access-control-allow-origin"] == origin


def test_cors_still_rejects_unknown_origins(client):
    r = client.options(f"{API}/auth/me", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "PUT"})
    assert r.status_code == 400
    assert "access-control-allow-origin" not in r.headers


# --- 3. audio content ---------------------------------------------------------------------

@pytest.mark.parametrize("data, mime", [
    (b"<html><script>alert(1)</script></html>" + b"\x00" * 200, "audio/webm"),
    (audio_bytes("ogg", 1), "audio/webm"),                  # real Ogg bytes, wrong declared type
    (WEBM, "audio/ogg"),
    (b"MZ\x90\x00" + b"\x00" * 200, "audio/mpeg"),
    (b"RIFF\x00\x00\x00\x00AVI " + b"\x00" * 200, "audio/wav"),
])
def test_audio_content_must_match_declared_type(client, pg_session, data, mime):
    ctx = ExamCtx(client, pg_session)
    test, r1, w1, s1 = ctx.ielts()
    attempt_id = ctx.start(test)
    r = ctx.upload(attempt_id, s1, data=data, mime=mime)
    assert r.status_code == 422, r.json()
    assert _state(ctx.detail(attempt_id), s1)["has_audio"] is False


@pytest.mark.parametrize("data, mime", [
    (WEBM, "audio/webm;codecs=opus"),
    (audio_bytes("ogg", 1), "audio/ogg"),
    (audio_bytes("mp4", 1), "audio/mp4"),
    (audio_bytes("mp3", 1), "audio/mpeg"),
    (audio_bytes("wav", 1), "audio/wav"),
])
def test_genuine_audio_signatures_are_accepted(client, pg_session, data, mime):
    ctx = ExamCtx(client, pg_session)
    test, r1, w1, s1 = ctx.ielts()
    attempt_id = ctx.start(test)
    assert ctx.upload(attempt_id, s1, data=data, mime=mime).status_code == 201


# --- 4. list sort parameter -----------------------------------------------------------------

@pytest.mark.parametrize("path", ["/lessons?sort=__class__", "/lessons?sort=-__init__", "/topics?sort=__class__",
                                  "/subjects?sort=__class__", "/grades?sort=__class__", "/schools?sort=__class__"])
def test_public_list_sort_never_raises_500(client, path):
    """Previously `?sort=__class__` made getattr() return a non-column and the
    public endpoint answered 500."""
    r = client.get(f"{API}{path}")
    assert r.status_code == 200, r.text


def test_users_cannot_be_ordered_by_password_hash(client, pg_session):
    admin = _user(pg_session, "Admin")
    h = {"Authorization": f"Bearer {_login(client, admin).json()['data']['access_token']}"}
    by_hash = client.get(f"{API}/users?sort=password_hash&per_page=100", headers=h)
    by_created = client.get(f"{API}/users?sort=created_at&per_page=100", headers=h)
    assert by_hash.status_code == 200
    # password_hash is ignored: the order is exactly the fallback column's (created_at).
    assert [u["id"] for u in by_hash.json()["data"]["items"]] == [u["id"] for u in by_created.json()["data"]["items"]]
