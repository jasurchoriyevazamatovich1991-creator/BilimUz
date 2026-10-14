"""
Sprint 88 — end-to-end AI Center message flow against the real app, real
PostgreSQL, and real auth/rate-limiting (the `client`/`pg_session`
fixtures from conftest.py — same pattern as test_sprint86_refresh_cookie_
flow.py). The AI provider itself is swapped via
app.dependency_overrides[get_ai_provider] — never a real network call,
never a real API key, exactly like Sprint 86's AuthService fakes. This
proves the full router → auth → rate_limit_by_user → AIChatService →
provider chain works together for real, something the mock-based unit
tests in app/modules/ai/tests/ cannot (they construct AIChatService
directly, bypassing the router/auth/rate-limit layers entirely).

Requires TEST_DATABASE_URL and TEST_REDIS_URL (rate_limit_by_user needs
real Redis) — same requirement every other integration test in this
directory already has.

Access tokens are sent via an explicit `Authorization: Bearer <token>`
header on every request (same pattern as test_auth_rbac_integration.py)
— the TestClient's cookie jar (Sprint 86) only ever carries the refresh
token and CSRF cookie, never the access token.
"""
import uuid

import pytest

from app.core.security.password_service import PasswordService
from app.modules.ai.dependencies import get_ai_provider
from app.modules.ai.providers import AIResponse
from app.modules.roles.models import Role
from app.modules.users.models import User, UserStatus
from app.main import app


def _create_student(pg_session) -> tuple[str, str]:
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    email = f"ai-student-{uuid.uuid4()}@example.com"
    password = "Integration-T3st-P@ss2"
    user = User(
        role_id=role.id, first_name="AI", last_name="Student",
        email=email, password_hash=PasswordService().hash_password(password), status=UserStatus.ACTIVE,
    )
    pg_session.add(user)
    pg_session.flush()
    return email, password


def _login(client, email: str, password: str) -> dict[str, str]:
    """Logs in and returns the Authorization header to attach to every
    subsequent request."""
    response = client.post("/api/v1/auth/login", json={"identifier": email, "password": password})
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


class _FakeSuccessProvider:
    def generate(self, request):
        return AIResponse(content="Bu haqiqiy (fake, testda) AI javobi.", provider="fake", model="fake-model", tokens_used=42)


class _FakeRaisingProvider:
    def __init__(self, exc: Exception):
        self._exc = exc

    def generate(self, request):
        raise self._exc


@pytest.fixture(autouse=True)
def _clear_ai_provider_override():
    """Every test in this file overrides get_ai_provider itself — this
    guarantees the override is always removed afterward, even if a test
    fails, so it can never leak into an unrelated later test."""
    yield
    app.dependency_overrides.pop(get_ai_provider, None)


def test_send_message_end_to_end_with_a_configured_provider_returns_real_response(client, pg_session):
    email, password = _create_student(pg_session)
    auth = _login(client, email, password)
    app.dependency_overrides[get_ai_provider] = lambda: _FakeSuccessProvider()

    chat_resp = client.post("/api/v1/ai/chats", json={"title": "Fizika bo'yicha savol"}, headers=auth)
    assert chat_resp.status_code == 201
    chat_id = chat_resp.json()["data"]["id"]

    msg_resp = client.post(f"/api/v1/ai/chats/{chat_id}/messages", json={"content": "Nyutonning birinchi qonuni nima?"}, headers=auth)

    assert msg_resp.status_code == 200
    body = msg_resp.json()
    assert body["success"] is True
    assert body["data"]["assistant_message"]["message"] == "Bu haqiqiy (fake, testda) AI javobi."
    assert body["data"]["user_message"]["message"] == "Nyutonning birinchi qonuni nima?"


def test_send_message_persists_history_retrievable_via_get_chat(client, pg_session):
    email, password = _create_student(pg_session)
    auth = _login(client, email, password)
    app.dependency_overrides[get_ai_provider] = lambda: _FakeSuccessProvider()

    chat_id = client.post("/api/v1/ai/chats", json={}, headers=auth).json()["data"]["id"]
    client.post(f"/api/v1/ai/chats/{chat_id}/messages", json={"content": "Salom"}, headers=auth)

    detail = client.get(f"/api/v1/ai/chats/{chat_id}", headers=auth)
    assert detail.status_code == 200
    history = detail.json()["data"]["history"]
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"


def test_send_message_with_unconfigured_provider_returns_501_not_a_fake_success(client, pg_session):
    """Default behavior (AI_PROVIDER=none in this sandbox's .env) — the
    real get_ai_provider() dependency is deliberately NOT overridden
    here, proving the actual configured app, not a fake, still honestly
    refuses rather than fabricating a response."""
    email, password = _create_student(pg_session)
    auth = _login(client, email, password)

    chat_id = client.post("/api/v1/ai/chats", json={}, headers=auth).json()["data"]["id"]
    response = client.post(f"/api/v1/ai/chats/{chat_id}/messages", json={"content": "Salom"}, headers=auth)

    assert response.status_code == 501
    assert response.json()["success"] is False


@pytest.mark.parametrize(
    "exc_name,status_code",
    [
        ("auth", 502),
        ("rate_limited", 429),
        ("timeout", 504),
        ("unavailable", 503),
    ],
)
def test_provider_failure_modes_return_safe_error_responses_never_a_fake_success(client, pg_session, exc_name, status_code):
    from app.modules.ai.exceptions import (
        AIProviderAuthenticationException,
        AIProviderRateLimitedException,
        AIProviderTimeoutException,
        AIProviderUnavailableException,
    )

    exc_map = {
        "auth": AIProviderAuthenticationException("AI provayder konfiguratsiyasida xatolik. Administratorga murojaat qiling."),
        "rate_limited": AIProviderRateLimitedException("AI provayder hozir band. Birozdan so'ng qayta urining."),
        "timeout": AIProviderTimeoutException("AI provayderga yuborilgan so'rov vaqti tugadi. Birozdan so'ng qayta urining."),
        "unavailable": AIProviderUnavailableException("AI provayder bilan bog'lanib bo'lmadi. Birozdan so'ng qayta urining."),
    }
    email, password = _create_student(pg_session)
    auth = _login(client, email, password)
    app.dependency_overrides[get_ai_provider] = lambda: _FakeRaisingProvider(exc_map[exc_name])

    chat_id = client.post("/api/v1/ai/chats", json={}, headers=auth).json()["data"]["id"]
    response = client.post(f"/api/v1/ai/chats/{chat_id}/messages", json={"content": "Salom"}, headers=auth)

    assert response.status_code == status_code
    body = response.json()
    assert body["success"] is False
    # Safe error — never a stack trace, internal URL, or the provider's
    # raw body/headers leaking into the client-visible response.
    assert "Traceback" not in str(body)
    assert "api.anthropic.com" not in str(body)

    # The user's own message must still have been saved even though the
    # provider call failed (same guarantee the Sprint 9 unit tests cover
    # for the mocked service; this proves it end-to-end too).
    detail = client.get(f"/api/v1/ai/chats/{chat_id}", headers=auth)
    assert len(detail.json()["data"]["history"]) == 1
    assert detail.json()["data"]["history"][0]["role"] == "user"


def test_user_cannot_send_a_message_into_another_users_chat(client, pg_session):
    email_a, password_a = _create_student(pg_session)
    auth_a = _login(client, email_a, password_a)
    app.dependency_overrides[get_ai_provider] = lambda: _FakeSuccessProvider()
    chat_id = client.post("/api/v1/ai/chats", json={}, headers=auth_a).json()["data"]["id"]

    email_b, password_b = _create_student(pg_session)
    auth_b = _login(client, email_b, password_b)

    response = client.post(
        f"/api/v1/ai/chats/{chat_id}/messages", json={"content": "Boshqa odamning chatiga kirmoqchiman"}, headers=auth_b
    )
    assert response.status_code == 404


def test_unauthenticated_request_is_rejected(client, pg_session):
    email, password = _create_student(pg_session)
    auth = _login(client, email, password)
    chat_id = client.post("/api/v1/ai/chats", json={}, headers=auth).json()["data"]["id"]

    response = client.post(f"/api/v1/ai/chats/{chat_id}/messages", json={"content": "Salom"})  # no Authorization header at all
    assert response.status_code == 401


def test_empty_message_is_rejected_before_reaching_the_provider(client, pg_session):
    email, password = _create_student(pg_session)
    auth = _login(client, email, password)
    provider_was_called = {"value": False}

    class _AssertNeverCalledProvider:
        def generate(self, request):
            provider_was_called["value"] = True
            return AIResponse(content="should never happen", provider="fake")

    app.dependency_overrides[get_ai_provider] = lambda: _AssertNeverCalledProvider()
    chat_id = client.post("/api/v1/ai/chats", json={}, headers=auth).json()["data"]["id"]

    response = client.post(f"/api/v1/ai/chats/{chat_id}/messages", json={"content": "   "}, headers=auth)

    assert response.status_code == 422
    assert provider_was_called["value"] is False


def test_oversized_message_is_rejected_before_reaching_the_provider(client, pg_session):
    email, password = _create_student(pg_session)
    auth = _login(client, email, password)
    app.dependency_overrides[get_ai_provider] = lambda: _FakeSuccessProvider()
    chat_id = client.post("/api/v1/ai/chats", json={}, headers=auth).json()["data"]["id"]

    too_long = "a" * 4001  # MAX_MESSAGE_LENGTH is 4000
    response = client.post(f"/api/v1/ai/chats/{chat_id}/messages", json={"content": too_long}, headers=auth)

    assert response.status_code == 422


def test_per_user_rate_limit_is_enforced_on_the_real_endpoint(client, pg_session):
    """10 requests/minute per user (app/modules/ai/constants.py) — reuses
    the existing rate_limit_by_user() mechanism unchanged this sprint.
    A fresh user per test means no cross-test counter collision."""
    email, password = _create_student(pg_session)
    auth = _login(client, email, password)
    app.dependency_overrides[get_ai_provider] = lambda: _FakeSuccessProvider()
    chat_id = client.post("/api/v1/ai/chats", json={}, headers=auth).json()["data"]["id"]

    for _ in range(10):
        response = client.post(f"/api/v1/ai/chats/{chat_id}/messages", json={"content": "Salom"}, headers=auth)
        assert response.status_code != 429

    response = client.post(f"/api/v1/ai/chats/{chat_id}/messages", json={"content": "Salom"}, headers=auth)
    assert response.status_code == 429
