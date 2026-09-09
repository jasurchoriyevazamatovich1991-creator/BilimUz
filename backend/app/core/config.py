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
