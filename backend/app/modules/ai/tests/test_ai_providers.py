"""Unit tests for the AIProvider interface — proves the honest-refusal
behavior explicitly, same pattern as Sprint 8's provider tests."""
import pytest

from app.modules.ai.exceptions import AIProviderNotConfiguredException
from app.modules.ai.providers import AIRequest, UnconfiguredAIProvider


def test_unconfigured_provider_raises_not_silently_succeeds():
    provider = UnconfiguredAIProvider()
    with pytest.raises(AIProviderNotConfiguredException):
        provider.generate(AIRequest(prompt="Salom"))


def test_provider_not_configured_exception_is_501():
    assert AIProviderNotConfiguredException.status_code == 501


def test_ai_request_carries_history():
    from app.modules.ai.providers import AIMessage
    request = AIRequest(prompt="Davomi?", history=[AIMessage(role="user", content="Salom")])
    assert len(request.history) == 1
    assert request.history[0].role == "user"
