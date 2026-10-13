"""
Sprint 86 — config validation and CORS wiring for the refresh-token
cookie migration. No live services needed.
"""
import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _base_kwargs(**overrides):
    kwargs = {"ENVIRONMENT": "development"}
    kwargs.update(overrides)
    return kwargs


def test_samesite_defaults_to_lax():
    settings = Settings(**_base_kwargs())
    assert settings.REFRESH_TOKEN_COOKIE_SAMESITE == "lax"


@pytest.mark.parametrize("value", ["lax", "Lax", "STRICT", "none", "None"])
def test_samesite_accepts_known_values_case_insensitively(value):
    settings = Settings(**_base_kwargs(REFRESH_TOKEN_COOKIE_SAMESITE=value))
    assert settings.REFRESH_TOKEN_COOKIE_SAMESITE == value.lower()


def test_samesite_rejects_unknown_value():
    with pytest.raises(ValidationError):
        Settings(**_base_kwargs(REFRESH_TOKEN_COOKIE_SAMESITE="sometimes"))


def test_cookie_domain_defaults_to_none_host_only():
    settings = Settings(**_base_kwargs())
    assert settings.REFRESH_TOKEN_COOKIE_DOMAIN is None


def test_refresh_token_cookie_name_has_a_safe_default():
    settings = Settings(**_base_kwargs())
    assert settings.REFRESH_TOKEN_COOKIE_NAME == "refresh_token"


def test_cors_allows_the_csrf_header_frontend_must_send():
    """Without X-CSRF-Token in allow_headers, the browser's own CORS
    preflight (OPTIONS) would block the header before it ever reaches
    core/security/csrf.py — this would silently break every refresh
    past the access token's lifetime, so it is pinned directly against
    the actual middleware configuration in app.main, not re-derived."""
    from app.main import app

    cors_middleware = next(
        m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"
    )
    allow_headers = cors_middleware.kwargs.get("allow_headers", [])
    assert "X-CSRF-Token" in allow_headers


def test_cors_still_allows_credentials():
    """allow_credentials=True is what makes the browser actually send
    the refresh/csrf cookies cross-port in dev — a regression here would
    silently break the whole cookie flow."""
    from app.main import app

    cors_middleware = next(
        m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"
    )
    assert cors_middleware.kwargs.get("allow_credentials") is True
