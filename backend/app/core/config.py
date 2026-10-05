"""
Application-wide configuration.
Single source of truth for environment-driven settings — never hardcode
secrets, hosts, or credentials anywhere else in the codebase.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    APP_NAME: str = "BilimUz"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/bilimuz"

    # Redis (cache, rate limiting)
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Security
    VERIFICATION_CODE_TTL_MINUTES: int = 5
    VERIFICATION_CODE_MAX_ATTEMPTS: int = 5

    # Encryption at rest (Sprint 8 — settings module: SMTP/payment/AI secrets)
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # If this key is ever lost, every encrypted row becomes permanently unreadable — no recovery path.
    FILE_ENCRYPTION_KEY: str = "CHANGE_ME_IN_PRODUCTION_GENERATE_A_REAL_FERNET_KEY"

    # Media storage (Sprint 27 — R2). STORAGE_BACKEND defaults to
    # "local" so every existing deployment/dev environment is
    # completely unaffected unless explicitly switched to "r2" — the
    # R2_* values below are never read at all in the default configuration.
    STORAGE_BACKEND: str = "local"  # "local" | "r2"
    R2_ACCOUNT_ID: str = "CHANGE_ME_IN_PRODUCTION"
    R2_ACCESS_KEY_ID: str = "CHANGE_ME_IN_PRODUCTION"
    R2_SECRET_ACCESS_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    R2_BUCKET_NAME: str = "CHANGE_ME_IN_PRODUCTION"
    R2_ENDPOINT: str = ""  # optional override — defaults to https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    """Cached so .env is parsed once per process, not per request."""
    return Settings()


# Sprint 73 — SEC-1. Pure function (no app/FastAPI import), so it can be
# unit-tested in isolation against a hand-built Settings instance without
# spinning up the ASGI app. Called from app/main.py's startup handler.
#
# Every one of these fields ships with a public, repository-visible
# "CHANGE_ME_IN_PRODUCTION..." default (see above) purely so local/dev/CI
# environments work out of the box without a .env file. That same
# convenience becomes a critical vulnerability the moment ENVIRONMENT is
# "production" and an operator forgets to override them: JWT_SECRET_KEY
# left at its default lets anyone forge a valid access/refresh token for
# any user (including Super Admin) using only the public source code;
# FILE_ENCRYPTION_KEY left at its default lets anyone decrypt every
# encrypted-at-rest secret in the settings table. R2_* defaults are only
# checked when STORAGE_BACKEND == "r2" — the "local" backend never reads
# them, so flagging them unconditionally would be a false positive.
#
# Deliberately NOT a Pydantic model_validator on Settings itself: that
# would make EVERY environment (including this project's own test suite,
# which constructs Settings with defaults throughout) fail at import
# time. Scoped to an explicit, opt-in call instead.
_PRODUCTION_UNSAFE_DEFAULTS = {
    "JWT_SECRET_KEY": "CHANGE_ME_IN_PRODUCTION",
    "FILE_ENCRYPTION_KEY": "CHANGE_ME_IN_PRODUCTION_GENERATE_A_REAL_FERNET_KEY",
}
_PRODUCTION_UNSAFE_R2_DEFAULTS = {
    "R2_ACCOUNT_ID": "CHANGE_ME_IN_PRODUCTION",
    "R2_ACCESS_KEY_ID": "CHANGE_ME_IN_PRODUCTION",
    "R2_SECRET_ACCESS_KEY": "CHANGE_ME_IN_PRODUCTION",
    "R2_BUCKET_NAME": "CHANGE_ME_IN_PRODUCTION",
}


def validate_production_secrets(settings: Settings) -> list[str]:
    """Returns the list of setting names still at their unsafe default.
    Empty list == safe to start. Does NOT raise itself (kept a pure,
    easily-unit-testable function) — the caller (app/main.py) decides
    what to do with a non-empty result."""
    if settings.ENVIRONMENT != "production":
        return []

    unsafe = [name for name, default in _PRODUCTION_UNSAFE_DEFAULTS.items() if getattr(settings, name) == default]
    if settings.STORAGE_BACKEND == "r2":
        unsafe += [name for name, default in _PRODUCTION_UNSAFE_R2_DEFAULTS.items() if getattr(settings, name) == default]
    return unsafe
