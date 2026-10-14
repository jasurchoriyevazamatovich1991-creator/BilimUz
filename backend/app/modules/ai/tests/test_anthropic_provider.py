"""Sprint 88 — AnthropicProvider unit tests. httpx.post is mocked
throughout (patched on app.modules.ai.providers.httpx, the module's own
import), so these never make a real network call and never require a
real API key — matches the task's explicit "tests must not call a paid
real provider or require a real API key" requirement."""
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.modules.ai.exceptions import (
    AIProviderAuthenticationException,
    AIProviderException,
    AIProviderRateLimitedException,
    AIProviderTimeoutException,
    AIProviderUnavailableException,
)
from app.modules.ai.providers import AIMessage, AIRequest, AnthropicProvider

FAKE_API_KEY = "sk-ant-fake-key-never-a-real-credential"


def _provider() -> AnthropicProvider:
    return AnthropicProvider(api_key=FAKE_API_KEY, model="claude-3-5-haiku-20241022", max_output_tokens=512, timeout_seconds=10.0)


def _mock_response(status_code: int, json_data: dict | None = None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


@patch("app.modules.ai.providers.httpx.post")
def test_successful_generation_returns_real_content_and_token_usage(mock_post):
    mock_post.return_value = _mock_response(
        200,
        {"content": [{"type": "text", "text": "Salom! Qalaysiz?"}], "usage": {"output_tokens": 7}},
    )

    response = _provider().generate(AIRequest(prompt="Salom"))

    assert response.content == "Salom! Qalaysiz?"
    assert response.provider == "anthropic"
    assert response.model == "claude-3-5-haiku-20241022"
    assert response.tokens_used == 7


@patch("app.modules.ai.providers.httpx.post")
def test_sends_history_and_prompt_as_messages(mock_post):
    mock_post.return_value = _mock_response(200, {"content": [{"type": "text", "text": "Javob"}], "usage": {"output_tokens": 1}})

    request = AIRequest(prompt="Yangi savol", history=[AIMessage(role="user", content="Eski savol"), AIMessage(role="assistant", content="Eski javob")])
    _provider().generate(request)

    sent_payload = mock_post.call_args.kwargs["json"]
    assert sent_payload["messages"] == [
        {"role": "user", "content": "Eski savol"},
        {"role": "assistant", "content": "Eski javob"},
        {"role": "user", "content": "Yangi savol"},
    ]


@patch("app.modules.ai.providers.httpx.post")
def test_api_key_is_sent_only_in_header_never_in_body_or_exception(mock_post):
    mock_post.return_value = _mock_response(200, {"content": [{"type": "text", "text": "ok"}], "usage": {}})

    _provider().generate(AIRequest(prompt="Salom"))

    sent_headers = mock_post.call_args.kwargs["headers"]
    sent_payload = mock_post.call_args.kwargs["json"]
    assert sent_headers["x-api-key"] == FAKE_API_KEY
    assert FAKE_API_KEY not in str(sent_payload)


@patch("app.modules.ai.providers.httpx.post")
def test_timeout_raises_ai_provider_timeout_exception(mock_post):
    mock_post.side_effect = httpx.TimeoutException("timed out")
    with pytest.raises(AIProviderTimeoutException) as exc_info:
        _provider().generate(AIRequest(prompt="Salom"))
    assert FAKE_API_KEY not in str(exc_info.value.message)


@patch("app.modules.ai.providers.httpx.post")
def test_connection_failure_raises_ai_provider_unavailable_exception(mock_post):
    mock_post.side_effect = httpx.ConnectError("connection refused")
    with pytest.raises(AIProviderUnavailableException):
        _provider().generate(AIRequest(prompt="Salom"))


@pytest.mark.parametrize("status_code", [401, 403])
@patch("app.modules.ai.providers.httpx.post")
def test_auth_failure_raises_ai_provider_authentication_exception(mock_post, status_code):
    mock_post.return_value = _mock_response(status_code, {"error": {"message": "invalid x-api-key"}})
    with pytest.raises(AIProviderAuthenticationException) as exc_info:
        _provider().generate(AIRequest(prompt="Salom"))
    # The safe message never echoes the provider's raw error body.
    assert "invalid x-api-key" not in str(exc_info.value.message)
    assert FAKE_API_KEY not in str(exc_info.value.message)


@patch("app.modules.ai.providers.httpx.post")
def test_rate_limited_raises_ai_provider_rate_limited_exception(mock_post):
    mock_post.return_value = _mock_response(429, {"error": {"message": "rate limited"}})
    with pytest.raises(AIProviderRateLimitedException):
        _provider().generate(AIRequest(prompt="Salom"))


@patch("app.modules.ai.providers.httpx.post")
def test_provider_server_error_raises_ai_provider_unavailable_exception(mock_post):
    mock_post.return_value = _mock_response(500, {"error": {"message": "internal server error"}})
    with pytest.raises(AIProviderUnavailableException):
        _provider().generate(AIRequest(prompt="Salom"))


@patch("app.modules.ai.providers.httpx.post")
def test_unexpected_status_raises_generic_ai_provider_exception(mock_post):
    mock_post.return_value = _mock_response(418, {})
    with pytest.raises(AIProviderException):
        _provider().generate(AIRequest(prompt="Salom"))


@patch("app.modules.ai.providers.httpx.post")
def test_malformed_json_response_raises_generic_ai_provider_exception(mock_post):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.side_effect = ValueError("not json")
    mock_post.return_value = resp
    with pytest.raises(AIProviderException):
        _provider().generate(AIRequest(prompt="Salom"))


@patch("app.modules.ai.providers.httpx.post")
def test_empty_content_raises_generic_ai_provider_exception(mock_post):
    mock_post.return_value = _mock_response(200, {"content": [], "usage": {"output_tokens": 0}})
    with pytest.raises(AIProviderException):
        _provider().generate(AIRequest(prompt="Salom"))


@patch("app.modules.ai.providers.httpx.post")
def test_request_uses_bounded_timeout(mock_post):
    mock_post.return_value = _mock_response(200, {"content": [{"type": "text", "text": "ok"}], "usage": {}})
    AnthropicProvider(api_key=FAKE_API_KEY, model="claude-3-5-haiku-20241022", max_output_tokens=512, timeout_seconds=12.5).generate(
        AIRequest(prompt="Salom")
    )
    assert mock_post.call_args.kwargs["timeout"] == 12.5


@patch("app.modules.ai.providers.httpx.post")
def test_request_respects_max_output_tokens_setting(mock_post):
    mock_post.return_value = _mock_response(200, {"content": [{"type": "text", "text": "ok"}], "usage": {}})
    AnthropicProvider(api_key=FAKE_API_KEY, model="claude-3-5-haiku-20241022", max_output_tokens=256, timeout_seconds=10.0).generate(
        AIRequest(prompt="Salom")
    )
    assert mock_post.call_args.kwargs["json"]["max_tokens"] == 256
