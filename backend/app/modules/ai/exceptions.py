"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class ChatNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "CHAT_NOT_FOUND"


class StudyPlanNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "STUDY_PLAN_NOT_FOUND"


class AIProviderException(AppException):
    """Sprint 88 — common base for every AIProvider failure mode, so
    AIChatService.send_message can catch and usage-log ALL of them
    uniformly (not just "not configured") with one except clause. Never
    constructed directly — always one of the specific subclasses below,
    each carrying a safe, generic, pre-written message (never a raw
    provider response body, stack trace, or the API key itself — see
    providers.py's AnthropicProvider for where upstream details are
    logged server-side only, never put into one of these messages)."""
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "AI_PROVIDER_ERROR"


class AIProviderNotConfiguredException(AIProviderException):
    """Raised by AIProvider.generate() when no real vendor is wired in —
    either AI_PROVIDER=none (the honest Sprint 9 default), or
    AI_PROVIDER=anthropic with AI_API_KEY still at its placeholder
    default (Sprint 88 — fail safely on missing credentials rather than
    attempting a doomed real call). An honest refusal, not a fake
    response — see providers.py."""
    status_code = status.HTTP_501_NOT_IMPLEMENTED
    error_code = "AI_PROVIDER_NOT_CONFIGURED"


class AIProviderAuthenticationException(AIProviderException):
    """Sprint 88 — the provider rejected our own API key (401/403).
    This is a server-side configuration problem, never the end user's
    fault, so the message never implies the user did anything wrong."""
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "AI_PROVIDER_AUTH_FAILED"


class AIProviderRateLimitedException(AIProviderException):
    """Sprint 88 — the provider itself rate-limited or quota-exhausted
    this backend (HTTP 429 from the provider), distinct from this
    project's own per-user rate_limit_by_user() (which runs first, at
    the router layer, before the provider is ever called)."""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "AI_PROVIDER_RATE_LIMITED"


class AIProviderTimeoutException(AIProviderException):
    """Sprint 88 — the provider call exceeded AI_REQUEST_TIMEOUT_SECONDS
    without responding."""
    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    error_code = "AI_PROVIDER_TIMEOUT"


class AIProviderUnavailableException(AIProviderException):
    """Sprint 88 — connection failure reaching the provider, or the
    provider returned a 5xx of its own."""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "AI_PROVIDER_UNAVAILABLE"
