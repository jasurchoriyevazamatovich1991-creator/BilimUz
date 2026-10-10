"""Sprint 73 — SEC-1. Pure unit tests, no DB/HTTP/app import required —
`validate_production_secrets()` is a plain function over a Settings
instance, deliberately kept that way so this file never needs
TEST_DATABASE_URL or a running app.

Sprint 81 — Package 1 (S81-AUDIT-001 / S81-AUDIT-004) extended this
file with: (a) `ENVIRONMENT` allow-list validation tests (unset, empty
string, invalid value, and every valid value), and (b) `"staging"`
secret-safety tests — staging is now a GUARDED environment, replacing
the old `test_staging_environment_is_never_flagged` test, which
encoded the exact defect that sprint fixed (staging silently exempt
from every secret check).

Sprint 81 — Package 1 Follow-up (fail-closed ENVIRONMENT) further
replaces `test_environment_unset_defaults_to_development_and_is_not_
rejected` (below, renamed) with its exact inverse: ENVIRONMENT is now a
REQUIRED field with no default, so "not supplied at all" is no longer
a safe, silently-accepted case — it is now rejected exactly like an
empty/invalid value. Also removes `test_test_environment_is_never_
flagged_even_with_default_secrets`: a repo-wide search before this
follow-up confirmed "test" is not actually used as an ENVIRONMENT
value anywhere in this project (no CI workflow exists here, and
backend/conftest.py never sets ENVIRONMENT — pytest runs pick it up
from backend/.env's own explicit "development" line), so Package 1's
inclusion of "test" in the allow-list was speculative and has been
dropped; this task's own spec explicitly lists only development/
staging/production as valid. A whitespace-only-value test was added
(not previously considered).

See test_startup_secret_validation.py (same directory) for the
real-FastAPI-app-startup-path regression tests — kept in a separate
file deliberately, since this file's whole design point is staying
import-light (no `app.main`/app import, no TEST_DATABASE_URL
requirement)."""
import pytest
from pydantic import ValidationError

from app.core.config import VALID_ENVIRONMENTS, Settings, validate_production_secrets


def _settings(**overrides) -> Settings:
    """Settings() reads a real .env file by default (model_config has
    env_file=".env"); _env_file=None forces pure-default construction so
    these tests are 100% deterministic regardless of what's in this
    sandbox's backend/.env."""
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


# --- Sprint 81 — ENVIRONMENT allow-list validation (S81-AUDIT-001) ---


def test_environment_completely_unset_is_rejected_fail_closed():
    """Sprint 81 — Package 1 Follow-up, scenario 1: ENVIRONMENT not
    supplied by ANY source (no env var, no .env file — _env_file=None
    disables that source too) must now FAIL LOUDLY rather than
    silently falling back to "development". This is the exact
    behavior change from Package 1: there, this same scenario asserted
    `settings.ENVIRONMENT == "development"` and a clean pass — that
    was the residual gap (a real deploy that simply forgets to set
    ENVIRONMENT would previously boot unprotected). ENVIRONMENT has no
    class default anymore, so Pydantic itself raises "Field required"."""
    with pytest.raises(ValidationError, match="ENVIRONMENT"):
        _settings()


def test_environment_empty_string_is_rejected():
    """Scenario 2: an explicitly-empty ENVIRONMENT (e.g. `ENVIRONMENT=`
    left behind in a .env/compose file) must fail loudly at startup,
    not be silently accepted and then silently skip every secret
    check (the exact pre-fix behavior: "" != "production" so the old
    gate let it straight through)."""
    with pytest.raises(ValidationError):
        _settings(ENVIRONMENT="")


def test_environment_whitespace_only_is_rejected():
    """Scenario 2 (whitespace variant, explicitly called out in this
    follow-up's own spec): a value that is technically non-empty but
    carries no real content (`"   "`) must be rejected exactly like an
    empty string — not previously considered in Package 1."""
    with pytest.raises(ValidationError):
        _settings(ENVIRONMENT="   ")
    with pytest.raises(ValidationError):
        _settings(ENVIRONMENT="\t\n")


def test_environment_invalid_value_is_rejected():
    """Scenario 3: a typo'd ENVIRONMENT value must fail loudly rather
    than being silently treated as some other environment. Two
    different plausible typos are checked so this isn't tied to one
    specific string."""
    with pytest.raises(ValidationError):
        _settings(ENVIRONMENT="prodution")
    with pytest.raises(ValidationError):
        _settings(ENVIRONMENT="stagng")


@pytest.mark.parametrize("value", sorted(VALID_ENVIRONMENTS))
def test_every_documented_valid_environment_value_is_accepted(value):
    """Scenario 4: development/staging/production must all construct
    cleanly. Parametrized directly over VALID_ENVIRONMENTS (not a
    hardcoded list) so this test automatically tracks the real
    allow-list rather than drifting from it."""
    settings = _settings(ENVIRONMENT=value)
    assert settings.ENVIRONMENT == value


def test_valid_environments_is_exactly_the_three_documented_values():
    """This follow-up's own spec requires EXACTLY {development,
    staging, production} — explicitly no longer "test" (removed; see
    module docstring for why). A set-equality check so a future,
    unreviewed addition/removal is caught immediately."""
    assert VALID_ENVIRONMENTS == {"development", "staging", "production"}


def test_environment_validation_error_never_includes_a_secret_value():
    """The ValidationError message must explain the problem (the bad
    ENVIRONMENT value, which is not itself a secret) without ever
    reflecting JWT_SECRET_KEY/FILE_ENCRYPTION_KEY/R2 credentials — this
    test constructs with those fields at non-default, recognizably
    "real" values and confirms none of them leak into the raised
    error's string representation."""
    with pytest.raises(ValidationError) as exc_info:
        _settings(
            ENVIRONMENT="not-a-real-environment",
            JWT_SECRET_KEY="super-secret-jwt-value-must-not-leak",
            FILE_ENCRYPTION_KEY="super-secret-fernet-value-must-not-leak",
        )
    message = str(exc_info.value)
    assert "super-secret-jwt-value-must-not-leak" not in message
    assert "super-secret-fernet-value-must-not-leak" not in message
    assert "not-a-real-environment" in message  # the actual problem IS named


# --- Sprint 81 — staging is now a guarded environment (S81-AUDIT-004) ---


def test_staging_with_default_jwt_and_encryption_secrets_is_now_flagged():
    """Replaces the old (pre-fix) `test_staging_environment_is_never_
    flagged` test, which encoded the exact S81-AUDIT-004 defect as
    "expected" behavior. Staging is a real, often internet-reachable
    pre-prod deployment and must get the same secret-safety gate as
    production."""
    settings = _settings(ENVIRONMENT="staging")
    unsafe = validate_production_secrets(settings)
    assert "JWT_SECRET_KEY" in unsafe
    assert "FILE_ENCRYPTION_KEY" in unsafe


def test_staging_with_real_secrets_overridden_is_safe():
    settings = _settings(
        ENVIRONMENT="staging",
        JWT_SECRET_KEY="a-real-64-byte-random-secret-generated-for-this-deployment",
        FILE_ENCRYPTION_KEY="dGhpcyBpcyBhIHJlYWwgZmVybmV0IGtleSBnZW5lcmF0ZWQ=",
    )
    assert validate_production_secrets(settings) == []


def test_staging_with_r2_storage_and_default_r2_credentials_is_flagged():
    settings = _settings(
        ENVIRONMENT="staging",
        JWT_SECRET_KEY="a-real-secret",
        FILE_ENCRYPTION_KEY="a-real-fernet-key",
        STORAGE_BACKEND="r2",
    )
    unsafe = validate_production_secrets(settings)
    assert "R2_ACCOUNT_ID" in unsafe
    assert "R2_ACCESS_KEY_ID" in unsafe
    assert "R2_SECRET_ACCESS_KEY" in unsafe
    assert "R2_BUCKET_NAME" in unsafe


def test_development_environment_is_never_flagged_even_with_default_secrets():
    settings = _settings(ENVIRONMENT="development")
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
