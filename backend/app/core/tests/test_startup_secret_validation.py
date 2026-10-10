"""Sprint 81 — Package 1 (S81-AUDIT-001 / S81-AUDIT-004), extended by
Package 1 Follow-up (fail-closed ENVIRONMENT) with
`test_fully_unset_environment_refuses_to_start_for_real` and
`test_whitespace_only_environment_refuses_to_start_for_real` below.

Deliberately kept SEPARATE from test_config_production_validation.py,
which is a pure, app-import-free unit-test file by design (see its own
module docstring). The task spec explicitly requires verifying that
`validate_production_secrets()` is actually invoked on the REAL FastAPI
application startup path (`app/main.py`'s `on_startup()` handler), not
just as an isolated function call — so this file imports `app.main` and
drives its real `@app.on_event("startup")` handler through
`fastapi.testclient.TestClient` used as a context manager (which is
what triggers FastAPI/Starlette lifespan startup events).

This does NOT require a live Postgres/Redis: `app.main`'s own
`on_startup()` only calls `validate_production_secrets()` and logs — it
never touches the database, and importing `app.main` only constructs a
(lazy, unconnected) SQLAlchemy engine object, confirmed directly in
this sandbox with Postgres/Redis both stopped.

`get_settings()` is `@lru_cache`'d and `app/main.py` reads
`settings = get_settings()` at MODULE level, so each test that wants a
different ENVIRONMENT/secret combination must, in this order:
  1. set the relevant env vars,
  2. clear `get_settings`'s cache,
  3. (re)import `app.main` fresh (importlib.reload if already imported),
then wrap `main_module.app` in `TestClient(...)` as a context manager.
Every test cleans up every env var it set (via `monkeypatch`, which
auto-reverts) and clears the settings cache again afterward, so no test
here leaks environment state into any other test in the suite —
including the many existing tests that import `app.main`'s `app` via
the `client`/`pg_session` fixtures in `backend/conftest.py`.
"""
import importlib

import pytest
from fastapi.testclient import TestClient

import app.core.config as config_module


def _import_fresh_main():
    """Reloads app.main against whatever env vars are currently set,
    after clearing the get_settings() cache, so this module's
    module-level `settings = get_settings()` and `app = FastAPI(...)`
    are rebuilt from the current environment."""
    config_module.get_settings.cache_clear()
    import app.main as main_module  # noqa: PLC0415 — intentionally deferred

    importlib.reload(main_module)
    return main_module


@pytest.fixture(autouse=True)
def _reset_settings_cache_after_each_test():
    """Belt-and-suspenders cleanup: even though every test below uses
    monkeypatch.setenv (auto-reverting), also force get_settings() to
    be rebuilt from the real environment again after this test, so a
    reload left mid-test never leaks into whichever test runs next
    (including tests in other files that import app.main's `app` via
    conftest.py's `client` fixture)."""
    yield
    config_module.get_settings.cache_clear()
    import app.main as main_module  # noqa: PLC0415

    importlib.reload(main_module)


def test_production_with_default_jwt_secret_refuses_to_start_for_real(monkeypatch):
    """Scenario 3 (task spec): production + placeholder JWT secret must
    refuse to start — verified through the REAL startup event, not a
    mocked/direct call to validate_production_secrets()."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")
    monkeypatch.setenv("FILE_ENCRYPTION_KEY", "a-real-fernet-key-for-this-test")
    main_module = _import_fresh_main()

    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        with TestClient(main_module.app):
            pass


def test_staging_with_default_jwt_secret_refuses_to_start_for_real(monkeypatch):
    """Scenario 4: staging + placeholder JWT secret must refuse to
    start — this is the exact real-startup-path regression for
    S81-AUDIT-004 (staging was previously silently exempt)."""
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("JWT_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")
    monkeypatch.setenv("FILE_ENCRYPTION_KEY", "a-real-fernet-key-for-this-test")
    main_module = _import_fresh_main()

    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        with TestClient(main_module.app):
            pass


def test_production_with_default_encryption_key_refuses_to_start_for_real(monkeypatch):
    """Scenario 5: production + placeholder FILE_ENCRYPTION_KEY must
    refuse to start, verified through the real startup event.

    FILE_ENCRYPTION_KEY is set explicitly to its known
    CHANGE_ME_IN_PRODUCTION... default rather than left unset, because
    this sandbox's own backend/.env happens to already override it to
    a non-default local-dev value — monkeypatch.setenv must win over
    that .env value for this test to actually exercise the placeholder
    case (confirmed: Settings' pydantic-settings env-var source takes
    priority over its env_file source, env vars set via os.environ
    always outrank the .env file)."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "a-real-jwt-secret-for-this-test")
    monkeypatch.setenv("FILE_ENCRYPTION_KEY", "CHANGE_ME_IN_PRODUCTION_GENERATE_A_REAL_FERNET_KEY")
    main_module = _import_fresh_main()

    with pytest.raises(RuntimeError, match="FILE_ENCRYPTION_KEY"):
        with TestClient(main_module.app):
            pass


def test_staging_with_default_encryption_key_refuses_to_start_for_real(monkeypatch):
    """Scenario 6: staging + placeholder FILE_ENCRYPTION_KEY must
    refuse to start, verified through the real startup event. See the
    comment in the production-equivalent test above for why
    FILE_ENCRYPTION_KEY is set explicitly rather than left unset."""
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("JWT_SECRET_KEY", "a-real-jwt-secret-for-this-test")
    monkeypatch.setenv("FILE_ENCRYPTION_KEY", "CHANGE_ME_IN_PRODUCTION_GENERATE_A_REAL_FERNET_KEY")
    main_module = _import_fresh_main()

    with pytest.raises(RuntimeError, match="FILE_ENCRYPTION_KEY"):
        with TestClient(main_module.app):
            pass


def test_production_with_real_secrets_starts_cleanly_for_real(monkeypatch):
    """Positive control: production with real-looking secrets must
    start without raising — confirms the fix does not over-block a
    correctly-configured production deployment."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "a-real-64-byte-random-secret-generated-for-this-deployment")
    monkeypatch.setenv("FILE_ENCRYPTION_KEY", "dGhpcyBpcyBhIHJlYWwgZmVybmV0IGtleSBnZW5lcmF0ZWQ=")
    main_module = _import_fresh_main()

    with TestClient(main_module.app):
        pass  # must not raise


def test_development_with_default_secrets_starts_cleanly_for_real(monkeypatch):
    """Backward-compat guard (task spec section C): the ordinary local
    dev workflow (ENVIRONMENT=development, every secret at its
    CHANGE_ME_IN_PRODUCTION default, exactly like backend/.env.example
    ships) must keep starting without any error."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    main_module = _import_fresh_main()

    with TestClient(main_module.app):
        pass  # must not raise


def test_unrecognized_environment_value_refuses_to_start_for_real(monkeypatch):
    """Scenario 9, exercised at the real startup path: constructing the
    real app against a typo'd ENVIRONMENT must fail loudly (a Pydantic
    ValidationError surfacing from get_settings()), not silently boot
    in some unintended mode."""
    monkeypatch.setenv("ENVIRONMENT", "prodution")

    with pytest.raises(Exception, match="not a recognized environment"):
        _import_fresh_main()


def test_empty_environment_value_refuses_to_start_for_real(monkeypatch):
    """Scenario 2 (empty), exercised at the real startup path."""
    monkeypatch.setenv("ENVIRONMENT", "")

    with pytest.raises(Exception, match="not a recognized environment"):
        _import_fresh_main()


def test_whitespace_only_environment_refuses_to_start_for_real(monkeypatch):
    """Scenario 2 (whitespace-only), exercised at the real startup path."""
    monkeypatch.setenv("ENVIRONMENT", "   ")

    with pytest.raises(Exception, match="not a recognized environment"):
        _import_fresh_main()


def test_fully_unset_environment_refuses_to_start_for_real(monkeypatch):
    """Sprint 81 — Package 1 Follow-up, scenario 1, exercised at the
    REAL startup path: this is the core behavior change. Unlike the
    other tests in this file, this one must simulate ENVIRONMENT being
    absent from EVERY source Settings() would consult — not just the
    OS environment (`monkeypatch.delenv`), but also backend/.env itself
    (which, in this sandbox, explicitly sets `ENVIRONMENT=development`
    for local-dev convenience — confirmed by direct inspection). A real
    production deployment that forgets to set ENVIRONMENT would have no
    such .env fallback either, so this test repoints `Settings`' own
    `model_config["env_file"]` at a path that does not exist, via
    monkeypatch (auto-reverted after the test — the real backend/.env
    file on disk is never touched), to faithfully reproduce "nothing,
    anywhere, supplies ENVIRONMENT"."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setitem(
        config_module.Settings.model_config,
        "env_file",
        "/nonexistent/no-such-env-file-for-this-test.env",
    )

    with pytest.raises(Exception, match="[Ff]ield required|ENVIRONMENT"):
        _import_fresh_main()
