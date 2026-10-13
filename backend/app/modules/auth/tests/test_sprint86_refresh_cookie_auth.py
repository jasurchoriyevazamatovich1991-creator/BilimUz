"""
Sprint 86 — refresh-token cookie migration. Router-level tests using
`TestClient(app)` with `get_auth_service` overridden to a fake — this
needs NO live PostgreSQL or Redis (the `rate_limit()` dependency's
module-level `redis_client` is monkeypatched to an in-memory fake), so
it runs in every environment via `pytest app/ -q`, unlike the real-DB
`client` fixture in conftest.py (used instead by the companion
tests/integration/test_sprint86_refresh_cookie_flow.py for genuine
end-to-end coverage against real Postgres).

What this file proves at the HTTP-response level (the one thing a
service-level test, like the pre-existing app/modules/auth/tests/
test_auth_service.py, structurally cannot: AuthService returns a plain
TokenPair, it has no idea cookies exist — that translation only happens
in router.py):
  - login/refresh never put refresh_token in the JSON body.
  - login/refresh set a cookie named settings.REFRESH_TOKEN_COOKIE_NAME
    with HttpOnly, the configured SameSite, and the configured Path.
  - refresh/logout reject a request with no refresh_token cookie.
  - refresh/logout reject a request whose CSRF header doesn't match (or
    is missing) the csrf_token cookie.
  - logout clears both cookies when the CSRF check passes.
"""
import re

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security.cookies import CSRF_COOKIE_NAME
from app.core.security.schemas import TokenPair
from app.main import app
from app.modules.auth.router import get_auth_service


class _FakeRedis:
    """In-memory stand-in for app.core.redis_client.redis_client — the
    exact two methods rate_limit()'s closure calls, nothing more."""

    def __init__(self):
        self._counts: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    def expire(self, key: str, seconds: int) -> None:
        pass


class _FakeAuthService:
    """Mirrors AuthService's public login/refresh/logout signatures
    exactly (see app/modules/auth/service.py) — router.py only ever
    calls these three, through the Depends(get_auth_service) override."""

    def login(self, identifier, password, ip, device):
        if password == "wrong":
            from app.core.exceptions import InvalidCredentialsException

            raise InvalidCredentialsException("Login yoki parol noto'g'ri")
        return TokenPair(access_token="fake-access-token", refresh_token="fake-refresh-token")

    def refresh(self, refresh_token: str) -> TokenPair:
        if refresh_token != "valid-refresh-cookie-value":
            from app.core.exceptions import InvalidTokenException

            raise InvalidTokenException("Refresh token yaroqsiz")
        return TokenPair(access_token="new-access-token", refresh_token="rotated-refresh-token")

    def logout(self, refresh_token: str) -> None:
        pass


@pytest.fixture
def fake_redis(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr("app.core.middleware.rate_limit.redis_client", fake)
    return fake


@pytest.fixture
def test_client(fake_redis):
    app.dependency_overrides[get_auth_service] = lambda: _FakeAuthService()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_auth_service, None)


def _set_cookie_headers(response, name: str) -> list[str]:
    return [h for h in response.headers.get_list("set-cookie") if h.startswith(f"{name}=")]


def test_login_omits_refresh_token_from_json_body(test_client):
    response = test_client.post("/api/v1/auth/login", json={"identifier": "x@x.com", "password": "right"})
    assert response.status_code == 200
    body = response.json()
    assert body["data"] == {"access_token": "fake-access-token", "token_type": "bearer"}
    assert "refresh_token" not in body["data"]


def test_login_sets_httponly_refresh_cookie_with_expected_attributes(test_client):
    settings = get_settings()
    response = test_client.post("/api/v1/auth/login", json={"identifier": "x@x.com", "password": "right"})

    cookie_headers = _set_cookie_headers(response, settings.REFRESH_TOKEN_COOKIE_NAME)
    assert len(cookie_headers) == 1
    header = cookie_headers[0].lower()
    assert "httponly" in header
    assert f"samesite={settings.REFRESH_TOKEN_COOKIE_SAMESITE}" in header
    assert f"path={settings.API_V1_PREFIX}/auth".lower() in header
    assert "fake-refresh-token" in cookie_headers[0]


def test_login_sets_readable_csrf_cookie_not_httponly(test_client):
    response = test_client.post("/api/v1/auth/login", json={"identifier": "x@x.com", "password": "right"})
    cookie_headers = _set_cookie_headers(response, CSRF_COOKIE_NAME)
    assert len(cookie_headers) == 1
    header = cookie_headers[0].lower()
    assert "httponly" not in header
    assert "path=/" in header


def test_login_failure_sets_no_cookies(test_client):
    response = test_client.post("/api/v1/auth/login", json={"identifier": "x@x.com", "password": "wrong"})
    assert response.status_code == 401
    assert response.headers.get_list("set-cookie") == []


def _csrf_cookie_value(response) -> str:
    header = _set_cookie_headers(response, CSRF_COOKIE_NAME)[0]
    return re.match(rf"{CSRF_COOKIE_NAME}=([^;]+)", header).group(1)


def test_refresh_without_cookie_is_rejected(test_client):
    """With neither cookie present, the CSRF check (listed first in the
    route's `dependencies=`) runs before the endpoint body's own
    refresh_token-cookie check — so this is a 403, not a 401. Either is
    a defensible "rejected", but the exact code matters for any client
    branching on it, so it's pinned here rather than left to drift."""
    response = test_client.post("/api/v1/auth/refresh")
    assert response.status_code == 403


def test_refresh_without_refresh_cookie_but_with_matching_csrf_is_rejected(test_client):
    """Isolates the endpoint body's own missing-refresh-cookie check
    (InvalidTokenException -> 401) from the CSRF dependency above, by
    satisfying CSRF first."""
    test_client.cookies.set(CSRF_COOKIE_NAME, "csrf-value")
    response = test_client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": "csrf-value"})
    assert response.status_code == 401


def test_refresh_without_csrf_header_is_rejected_even_with_valid_cookie(test_client):
    test_client.cookies.set("refresh_token", "valid-refresh-cookie-value")
    test_client.cookies.set(CSRF_COOKIE_NAME, "whatever-csrf-value")
    response = test_client.post("/api/v1/auth/refresh")
    assert response.status_code == 403
    assert response.json()["message"]


def test_refresh_with_mismatched_csrf_header_is_rejected(test_client):
    test_client.cookies.set("refresh_token", "valid-refresh-cookie-value")
    test_client.cookies.set(CSRF_COOKIE_NAME, "cookie-csrf-value")
    response = test_client.post(
        "/api/v1/auth/refresh", headers={"X-CSRF-Token": "a-different-value"}
    )
    assert response.status_code == 403


def test_refresh_with_matching_csrf_and_valid_cookie_rotates_tokens(test_client):
    test_client.cookies.set("refresh_token", "valid-refresh-cookie-value")
    test_client.cookies.set(CSRF_COOKIE_NAME, "matching-csrf-value")
    response = test_client.post(
        "/api/v1/auth/refresh", headers={"X-CSRF-Token": "matching-csrf-value"}
    )
    assert response.status_code == 200
    assert response.json()["data"] == {"access_token": "new-access-token", "token_type": "bearer"}
    # Rotation: a NEW refresh_token cookie value is set, not re-sent as-is.
    new_cookie = _set_cookie_headers(response, "refresh_token")[0]
    assert "rotated-refresh-token" in new_cookie
    assert "valid-refresh-cookie-value" not in new_cookie


def test_refresh_with_invalid_refresh_cookie_value_is_rejected(test_client):
    test_client.cookies.set("refresh_token", "not-the-right-value")
    test_client.cookies.set(CSRF_COOKIE_NAME, "csrf-value")
    response = test_client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": "csrf-value"})
    assert response.status_code == 401


def test_logout_without_csrf_header_is_rejected(test_client):
    test_client.cookies.set("refresh_token", "valid-refresh-cookie-value")
    test_client.cookies.set(CSRF_COOKIE_NAME, "csrf-value")
    response = test_client.post("/api/v1/auth/logout")
    assert response.status_code == 403


def test_logout_with_matching_csrf_clears_both_cookies(test_client):
    settings = get_settings()
    test_client.cookies.set("refresh_token", "valid-refresh-cookie-value")
    test_client.cookies.set(CSRF_COOKIE_NAME, "csrf-value")
    response = test_client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "csrf-value"})
    assert response.status_code == 204

    cleared = response.headers.get_list("set-cookie")
    refresh_clear = next(h for h in cleared if h.startswith(f"{settings.REFRESH_TOKEN_COOKIE_NAME}="))
    csrf_clear = next(h for h in cleared if h.startswith(f"{CSRF_COOKIE_NAME}="))
    # A cleared cookie is set with an empty/expired value (Starlette's
    # delete_cookie behavior) — both must still carry the SAME path the
    # cookie was originally scoped to, or real browsers won't clear it.
    assert f"path={settings.API_V1_PREFIX}/auth".lower() in refresh_clear.lower()
    assert "path=/" in csrf_clear.lower()


def test_logout_with_no_refresh_cookie_is_idempotent_given_valid_csrf(test_client):
    """No refresh cookie at all (already logged out elsewhere) must not
    error — matches AuthService.logout()'s pre-existing idempotent
    contract (app/modules/auth/service.py)."""
    test_client.cookies.set(CSRF_COOKIE_NAME, "csrf-value")
    response = test_client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "csrf-value"})
    assert response.status_code == 204
