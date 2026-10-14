"""Sprint 88 — select_ai_provider() unit tests. Pure function over a
hand-built Settings instance (same _settings() pattern as
app/core/tests/test_config_production_validation.py) — no env vars, no
lru_cache juggling, no real credentials needed."""
from app.core.config import Settings
from app.modules.ai.dependencies import select_ai_provider
from app.modules.ai.providers import AnthropicProvider, UnconfiguredAIProvider


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, ENVIRONMENT="development", **overrides)  # type: ignore[call-arg]


def test_default_provider_is_unconfigured():
    provider = select_ai_provider(_settings())
    assert isinstance(provider, UnconfiguredAIProvider)


def test_ai_provider_none_is_unconfigured_even_with_a_real_looking_key():
    """AI_PROVIDER=none always wins — a leftover AI_API_KEY value is
    simply never read in that mode (same reasoning as
    STORAGE_BACKEND=local never reading R2_* values)."""
    provider = select_ai_provider(_settings(AI_PROVIDER="none", AI_API_KEY="sk-ant-a-real-looking-key"))
    assert isinstance(provider, UnconfiguredAIProvider)


def test_anthropic_provider_with_placeholder_key_fails_safe_to_unconfigured():
    """AI_PROVIDER=anthropic but AI_API_KEY left at its public default —
    missing-configuration must fail safely (honest 501), never attempt
    a doomed real call."""
    provider = select_ai_provider(_settings(AI_PROVIDER="anthropic"))
    assert isinstance(provider, UnconfiguredAIProvider)


def test_anthropic_provider_with_a_real_key_is_wired_in():
    provider = select_ai_provider(
        _settings(AI_PROVIDER="anthropic", AI_API_KEY="sk-ant-a-real-key", AI_MODEL="claude-3-5-haiku-20241022", AI_MAX_OUTPUT_TOKENS=777, AI_REQUEST_TIMEOUT_SECONDS=15.0)
    )
    assert isinstance(provider, AnthropicProvider)
    assert provider._model == "claude-3-5-haiku-20241022"
    assert provider._max_output_tokens == 777
    assert provider._timeout_seconds == 15.0
