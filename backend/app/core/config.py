"""
Application-wide configuration.
Single source of truth for environment-driven settings — never hardcode
secrets, hosts, or credentials anywhere else in the codebase.
"""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Sprint 81 — Package 1 Follow-up (fail-closed ENVIRONMENT). The only
# environments this codebase's workflows actually use anywhere —
# confirmed by a repo-wide search before this change: docker-compose.yml
# and backend/.env.example both explicitly set "development"; nothing
# anywhere in this repository ever sets ENVIRONMENT to "test" (no CI
# workflow exists in this repo, and backend/conftest.py never sets
# ENVIRONMENT — pytest runs pick it up from backend/.env's own explicit
# "development" line, like any other local run). "test" was previously
# listed here (Sprint 81 Package 1) on a speculative assumption that
# turned out not to match anything real — removed in this follow-up so
# the allow-list reflects only environments this project actually uses,
# per this task's own explicit 3-value list. Kept as a single source of
# truth so the allow-list and the secret-safety gate below can never
# drift apart from each other.
VALID_ENVIRONMENTS = {"development", "staging", "production"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    APP_NAME: str = "BilimUz"
    API_V1_PREFIX: str = "/api/v1"
    # Sprint 81 — Package 1 Follow-up (fail-closed ENVIRONMENT).
    # DELIBERATELY NO DEFAULT (contrast with Package 1, which kept a
    # "development" default so an unset var fell back to it silently).
    # That silent fallback was itself the residual gap this follow-up
    # closes: a real deployment that simply forgets to set ENVIRONMENT
    # at all would previously boot as "development" and skip every
    # production-secret check — functionally the same hole as a typo,
    # just reached by omission instead. With no default, Pydantic
    # treats ENVIRONMENT as a REQUIRED field: if no source (env var,
    # .env file, or explicit kwarg) supplies it, Settings() construction
    # itself raises a `pydantic.ValidationError` ("Field required")
    # before the app can boot at all — "ishga tushmasligi kerak", not
    # merely "don't default to development". Every local/dev/test
    # workflow in THIS repo already sets ENVIRONMENT explicitly
    # (backend/.env, backend/.env.example, docker-compose.yml all say
    # `ENVIRONMENT=development` outright — confirmed by direct
    # inspection before this change), so none of them is affected.
    ENVIRONMENT: str  # development | staging | production — required, see validator below
    DEBUG: bool = False

    # Sprint 81 — Package 1 / Package 1 Follow-up. Validates whatever
    # value was actually supplied (this always runs — there is no
    # default left to skip validation for). Rejects:
    #   - a value outside VALID_ENVIRONMENTS (a typo like "prodution"),
    #   - an empty string (`ENVIRONMENT=` in a .env/compose file),
    #   - a whitespace-only string (`ENVIRONMENT="   "` — added in this
    #     follow-up; not previously considered, closes the same class
    #     of "looks set but isn't really" gap as the empty-string case).
    # Any of these on a real deployment would otherwise reach
    # validate_production_secrets() below and, since none of them
    # equals "production"/"staging" exactly, silently bypass the whole
    # secret-safety gate — the original S81-AUDIT-001/004 defect.
    @field_validator("ENVIRONMENT")
    @classmethod
    def _validate_environment(cls, v: str) -> str:
        if not v.strip() or v not in VALID_ENVIRONMENTS:
            raise ValueError(
                f"ENVIRONMENT={v!r} is not a recognized environment. "
                f"Must be one of {sorted(VALID_ENVIRONMENTS)} (whitespace-only "
                "and empty values are also rejected). Refusing to start — "
                "see Sprint 81 Package 1 Follow-up."
            )
        return v

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
# a real, internet-reachable deployment and an operator forgets to
# override them: JWT_SECRET_KEY left at its default lets anyone forge a
# valid access/refresh token for any user (including Super Admin) using
# only the public source code; FILE_ENCRYPTION_KEY left at its default
# lets anyone decrypt every encrypted-at-rest secret in the settings
# table. R2_* defaults are only checked when STORAGE_BACKEND == "r2" —
# the "local" backend never reads them, so flagging them unconditionally
# would be a false positive.
#
# Sprint 81 — Package 1 (S81-AUDIT-004). Originally gated on
# `ENVIRONMENT == "production"` only — "staging" (a real, often
# internet-reachable pre-prod deployment, per this file's own
# `# development | staging | production` comment) was silently exempt
# from every one of these checks. Gated on a `_GUARDED_ENVIRONMENTS`
# set instead of a single string so adding another guarded deployment
# tier in the future is a one-line change here, not a second forgotten
# `==` comparison elsewhere. "development" remains deliberately,
# permanently ungated — local dev must keep working with zero required
# .env overrides beyond the explicit `ENVIRONMENT=development` line
# every local/dev config in this repo already carries (see
# VALID_ENVIRONMENTS's own comment above for where).
#
# Deliberately NOT a Pydantic model_validator on Settings itself: that
# would make EVERY environment (including this project's own test suite,
# which constructs Settings with defaults throughout) fail at import
# time. Scoped to an explicit, opt-in call instead.
_GUARDED_ENVIRONMENTS = {"production", "staging"}
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
    what to do with a non-empty result.

    Sprint 81 — Package 1 (S81-AUDIT-004): guards every environment in
    `_GUARDED_ENVIRONMENTS` ("production" and "staging"), not just
    "production" — see that set's own docstring above for why."""
    if settings.ENVIRONMENT not in _GUARDED_ENVIRONMENTS:
        return []

    unsafe = [name for name, default in _PRODUCTION_UNSAFE_DEFAULTS.items() if getattr(settings, name) == default]
    if settings.STORAGE_BACKEND == "r2":
        unsafe += [name for name, default in _PRODUCTION_UNSAFE_R2_DEFAULTS.items() if getattr(settings, name) == default]
    return unsafe
