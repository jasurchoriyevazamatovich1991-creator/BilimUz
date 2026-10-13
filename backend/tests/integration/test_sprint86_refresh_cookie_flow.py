"""
Sprint 86 — end-to-end refresh-token-cookie lifecycle against the real
app, real PostgreSQL, real JWT/Argon2 (the `client`/`pg_session`
fixtures from conftest.py — same pattern as
test_auth_rbac_integration.py). This is the real-service counterpart to
app/modules/auth/tests/test_sprint86_refresh_cookie_auth.py, which
proves the same router-level contract against a fake AuthService with
no live dependencies; this file proves the real AuthService + real
RefreshToken rotation/revocation rows behave identically through the
cookie.

Requires TEST_DATABASE_URL (and, for rate-limit-adjacent assertions,
whatever Redis the `client` fixture's rate_limit() dependency reaches —
same requirement every other integration test in this directory
already has). Not executable in a sandbox without a live PostgreSQL —
see this sprint's final report for how this was verified (syntax/import
only, not executed) versus the real-DB-independent
test_sprint86_refresh_cookie_auth.py (actually run and passing).
"""
import uuid

from app.core.security.password_service import PasswordService
from app.modules.roles.models import Role
from app.modules.users.models import User, UserStatus


def _create_student(pg_session) -> tuple[str, str]:
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    email = f"student-{uuid.uuid4()}@example.com"
    password = "Integration-T3st-P@ss2"
    user = User(
        role_id=role.id, first_name="Cookie", last_name="Flow",
        email=email, password_hash=PasswordService().hash_password(password), status=UserStatus.ACTIVE,
    )
    pg_session.add(user)
    pg_session.flush()
    return email, password


def _login(client, email: str, password: str):
    response = client.post("/api/v1/auth/login", json={"identifier": email, "password": password})
    assert response.status_code == 200
    return response


def _csrf_header(client) -> dict[str, str]:
    token = client.cookies.get("csrf_token")
    assert token, "csrf_token cookie must be set after login"
    return {"X-CSRF-Token": token}


def test_full_login_refresh_logout_cycle_via_cookie(client, pg_session):
    email, password = _create_student(pg_session)
    _login(client, email, password)

    # The TestClient's own cookie jar now holds refresh_token + csrf_token,
    # exactly as a real browser's would — no token is read from the
    # response body anywhere in this test.
    refresh_response = client.post("/api/v1/auth/refresh", headers=_csrf_header(client))
    assert refresh_response.status_code == 200
    body = refresh_response.json()["data"]
    assert "access_token" in body
    assert "refresh_token" not in body

    logout_response = client.post("/api/v1/auth/logout", headers=_csrf_header(client))
    assert logout_response.status_code == 204


def test_refresh_token_rotation_invalidates_the_previous_cookie_value(client, pg_session):
    """The pre-existing rotation guarantee (AuthService.refresh() calls
    repo.revoke_refresh_token(stored) — unchanged by this sprint) must
    still hold when the token travels via cookie: reusing the OLD
    refresh_token value (captured before the first /refresh call) must
    be rejected on a second attempt, even though the cookie jar now
    holds the NEW one."""
    email, password = _create_student(pg_session)
    _login(client, email, password)
    old_refresh_token = client.cookies.get("refresh_token")

    first_refresh = client.post("/api/v1/auth/refresh", headers=_csrf_header(client))
    assert first_refresh.status_code == 200
    new_refresh_token = client.cookies.get("refresh_token")
    assert new_refresh_token != old_refresh_token

    # Manually force the cookie jar back to the OLD (now-revoked) value,
    # simulating a replayed/stale cookie.
    client.cookies.set("refresh_token", old_refresh_token)
    replay_response = client.post("/api/v1/auth/refresh", headers=_csrf_header(client))
    assert replay_response.status_code == 401


def test_logout_revokes_the_token_server_side_not_just_clears_the_cookie(client, pg_session):
    """Clearing the cookie alone would be a client-side-only logout — the
    server-side RefreshToken row must actually be revoked (pre-existing
    AuthService.logout() behavior), provable by attempting to refresh
    with the now-revoked value even if a client somehow still had it."""
    email, password = _create_student(pg_session)
    _login(client, email, password)
    refresh_token_value = client.cookies.get("refresh_token")

    logout_response = client.post("/api/v1/auth/logout", headers=_csrf_header(client))
    assert logout_response.status_code == 204

    # Simulate a client that captured the cookie value before logout and
    # tries to replay it directly (e.g. a stolen cookie used after the
    # legitimate user logged out elsewhere).
    client.cookies.set("refresh_token", refresh_token_value)
    client.cookies.set("csrf_token", client.cookies.get("csrf_token") or "irrelevant")
    replay_response = client.post("/api/v1/auth/refresh", headers=_csrf_header(client))
    assert replay_response.status_code == 401


def test_refresh_with_malformed_cookie_value_is_rejected_not_500(client, pg_session):
    email, password = _create_student(pg_session)
    _login(client, email, password)
    client.cookies.set("refresh_token", "not-even-a-jwt")

    response = client.post("/api/v1/auth/refresh", headers=_csrf_header(client))
    assert response.status_code == 401


def test_refresh_csrf_header_from_a_different_session_is_rejected(client, pg_session):
    """A CSRF token value that simply doesn't match the cookie at all
    (not just "missing") must still be rejected — guards against a copy
    of another valid-looking token being reused."""
    email, password = _create_student(pg_session)
    _login(client, email, password)

    response = client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": "totally-unrelated-value"})
    assert response.status_code == 403
