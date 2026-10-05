"""Sprint 73 — SEC-1. Pure unit tests, no DB/HTTP/app import required —
`validate_production_secrets()` is a plain function over a Settings
instance, deliberately kept that way so this file never needs
TEST_DATABASE_URL or a running app."""
from app.core.config import Settings, validate_production_secrets


def _settings(**overrides) -> Settings:
    """Settings() reads a real .env file by default (model_config has
    env_file=".env"); _env_file=None forces pure-default construction so
    these tests are 100% deterministic regardless of what's in this
    sandbox's backend/.env."""
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


def test_development_environment_is_never_flagged_even_with_default_secrets():
    settings = _settings(ENVIRONMENT="development")
    assert validate_production_secrets(settings) == []


def test_staging_environment_is_never_flagged():
    settings = _settings(ENVIRONMENT="staging")
    assert validate_production_secrets(settings) == []


def test_production_with_default_jwt_and_encryption_secrets_is_flagged():
    settings = _settings(ENVIRONMENT="production")
    unsafe = validate_production_secrets(settings)
    assert "JWT_SECRET_KEY" in unsafe
    assert "FILE_ENCRYPTION_KEY" in unsafe


def test_production_with_real_secrets_overridden_is_safe():
    settings = _settings(
        ENVIRONMENT="production",
        JWT_SECRET_KEY="a-real-64-byte-random-secret-generated-for-this-deployment",
        FILE_ENCRYPTION_KEY="dGhpcyBpcyBhIHJlYWwgZmVybmV0IGtleSBnZW5lcmF0ZWQ=",
    )
    assert validate_production_secrets(settings) == []


def test_production_with_local_storage_never_checks_r2_defaults():
    """STORAGE_BACKEND defaults to "local" — R2_* values are never read
    in that mode, so they must not be flagged even though they're still
    at their CHANGE_ME default."""
    settings = _settings(
        ENVIRONMENT="production",
        JWT_SECRET_KEY="a-real-secret",
        FILE_ENCRYPTION_KEY="a-real-fernet-key",
        STORAGE_BACKEND="local",
    )
    assert validate_production_secrets(settings) == []


def test_production_with_r2_storage_and_default_r2_credentials_is_flagged():
    settings = _settings(
        ENVIRONMENT="production",
        JWT_SECRET_KEY="a-real-secret",
        FILE_ENCRYPTION_KEY="a-real-fernet-key",
        STORAGE_BACKEND="r2",
    )
    unsafe = validate_production_secrets(settings)
    assert "R2_ACCOUNT_ID" in unsafe
    assert "R2_ACCESS_KEY_ID" in unsafe
    assert "R2_SECRET_ACCESS_KEY" in unsafe
    assert "R2_BUCKET_NAME" in unsafe


def test_production_with_r2_storage_and_real_r2_credentials_is_safe():
    settings = _settings(
        ENVIRONMENT="production",
        JWT_SECRET_KEY="a-real-secret",
        FILE_ENCRYPTION_KEY="a-real-fernet-key",
        STORAGE_BACKEND="r2",
        R2_ACCOUNT_ID="real-account",
        R2_ACCESS_KEY_ID="real-access-key",
        R2_SECRET_ACCESS_KEY="real-secret-key",
        R2_BUCKET_NAME="real-bucket",
    )
    assert validate_production_secrets(settings) == []
