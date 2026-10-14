"""
AIProvider interface + AIRequest/AIResponse — infrastructure used by
AIService, same relationship StorageBackend/EmailProvider have to their
respective services (Sprint 8). NOT a new architectural layer.

Sprint 9 scope boundary (superseded by Sprint 88 below): NO vendor SDK
(OpenAI, Anthropic, Gemini, or any other) was imported anywhere in this
module; UnconfiguredAIProvider was the only implementation.

Sprint 88 — AnthropicProvider is the first real implementation, added
exactly where the Sprint 9 docstring said a future sprint would add one:
here, as a second AIProvider, wired in via get_ai_provider()
(dependencies.py) with ZERO change to AIChatService. Still no vendor
SDK dependency (no `anthropic` PyPI package) — this calls the Messages
API directly over plain `httpx` (already a project dependency), which
satisfies the "no vendor SDK" spirit while being a genuinely real
integration, not a second placeholder.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import httpx

from app.core.logging import get_logger
from app.modules.ai.exceptions import (
    AIProviderAuthenticationException,
    AIProviderException,
    AIProviderNotConfiguredException,
    AIProviderRateLimitedException,
    AIProviderTimeoutException,
    AIProviderUnavailableException,
)

logger = get_logger(__name__)


@dataclass
class AIMessage:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class AIRequest:
    prompt: str
    history: list[AIMessage] = field(default_factory=list)


@dataclass
class AIResponse:
    content: str
    provider: str
    model: str | None = None
    tokens_used: int | None = None


class AIProvider(ABC):
    @abstractmethod
    def generate(self, request: AIRequest) -> AIResponse:
        """Raises on any failure (including 'not configured'). Returns
        normally only on a confirmed, real generated response."""
        ...


class UnconfiguredAIProvider(AIProvider):
    """The only AIProvider implementation this sprint. Honest, not fake:
    real vendor integration is explicitly deferred (see module docstring)."""

    def generate(self, request: AIRequest) -> AIResponse:
        raise AIProviderNotConfiguredException(
            "AI provayder ulanmagan — haqiqiy vendor integratsiyasi keyingi sprintga qoldirilgan"
        )


# Sprint 88 — Anthropic Messages API, called over plain httpx (no vendor
# SDK). Hardcoded, not configurable: the endpoint URL and API version
# are protocol details, not deployment choices — only the model,
# credentials, output cap, and timeout are configurable (Settings, see
# config.py), matching exactly what a real deployment might legitimately
# need to change.
_ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_API_VERSION = "2023-06-01"


class AnthropicProvider(AIProvider):
    """Real AIProvider implementation — calls Anthropic's Messages API.

    Security/privacy (Sprint 88 task requirements):
    - The API key is read once at construction (from Settings, backend
      env config only — see dependencies.py) and sent only in the
      `x-api-key` request header to Anthropic's own API; it is never
      logged, never put in an exception message, and never reaches the
      HTTP response sent back to our own clients.
    - Every failure path logs only a generic, non-identifying summary
      (provider name + HTTP status code) via the standard logger — never
      the prompt, the response text, or the raw provider response body.
      Every exception raised here carries a hand-written, safe, generic
      message — never an upstream body, header, or stack trace.
    - A single bounded `timeout` (AI_REQUEST_TIMEOUT_SECONDS) covers the
      whole request; there is no retry loop anywhere in this class —
      AIChatService.send_message calls generate() exactly once per
      end-user request, so a failure here surfaces immediately rather
      than silently re-attempting a possibly-costly generation.
    """

    def __init__(self, api_key: str, model: str, max_output_tokens: int, timeout_seconds: float):
        self._api_key = api_key
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._timeout_seconds = timeout_seconds

    def generate(self, request: AIRequest) -> AIResponse:
        messages = [{"role": m.role, "content": m.content} for m in request.history]
        messages.append({"role": "user", "content": request.prompt})

        try:
            response = httpx.post(
                _ANTHROPIC_API_URL,
                json={
                    "model": self._model,
                    "max_tokens": self._max_output_tokens,
                    "messages": messages,
                },
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": _ANTHROPIC_API_VERSION,
                    "content-type": "application/json",
                },
                timeout=self._timeout_seconds,
            )
        except httpx.TimeoutException:
            logger.warning("AI provider request timed out (provider=anthropic)")
            raise AIProviderTimeoutException(
                "AI provayderga yuborilgan so'rov vaqti tugadi. Birozdan so'ng qayta urining."
            )
        except httpx.RequestError:
            # Covers connection failures, DNS errors, TLS errors, etc. —
            # httpx.RequestError is the common base for all of these,
            # deliberately not narrowed further (the safe message is the
            # same regardless of which one occurred).
            logger.warning("AI provider request failed to connect (provider=anthropic)")
            raise AIProviderUnavailableException(
                "AI provayder bilan bog'lanib bo'lmadi. Birozdan so'ng qayta urining."
            )

        if response.status_code in (401, 403):
            logger.error("AI provider rejected our credentials (provider=anthropic, status=%s)", response.status_code)
            raise AIProviderAuthenticationException(
                "AI provayder konfiguratsiyasida xatolik. Administratorga murojaat qiling."
            )
        if response.status_code == 429:
            logger.warning("AI provider rate-limited this backend (provider=anthropic)")
            raise AIProviderRateLimitedException(
                "AI provayder hozir band. Birozdan so'ng qayta urining."
            )
        if response.status_code >= 500:
            logger.warning("AI provider returned a server error (provider=anthropic, status=%s)", response.status_code)
            raise AIProviderUnavailableException(
                "AI provayder vaqtincha ishlamayapti. Birozdan so'ng qayta urining."
            )
        if response.status_code != 200:
            logger.warning("AI provider returned an unexpected status (provider=anthropic, status=%s)", response.status_code)
            raise AIProviderException("AI provayderdan kutilmagan javob keldi.")

        try:
            data = response.json()
            content_blocks = data.get("content") or []
            text = "".join(block.get("text", "") for block in content_blocks if block.get("type") == "text")
            tokens_used = (data.get("usage") or {}).get("output_tokens")
        except (ValueError, AttributeError):
            logger.error("AI provider response could not be parsed (provider=anthropic)")
            raise AIProviderException("AI provayder javobini qayta ishlab bo'lmadi.")

        if not text:
            logger.warning("AI provider returned an empty generated response (provider=anthropic)")
            raise AIProviderException("AI provayderdan bo'sh javob keldi.")

        return AIResponse(content=text, provider="anthropic", model=self._model, tokens_used=tokens_used)
