"""
Sprint 84 — Package 2 (Redis test isolation).

Audit finding: `app/core/redis_client.py` builds its one module-level
`redis_client` from `settings.REDIS_URL` at import time, which defaults
to "redis://localhost:6379/0" — the exact host AND DB index a local
dev server uses by default (confirmed against `.env.example`). Unlike
PostgreSQL (`TEST_DATABASE_URL`, backend/conftest.py), there was no
dedicated test Redis configuration at all before this sprint, so any
integration test exercising the real `rate_limit()` dependency wrote
real keys into whatever Redis database REDIS_URL happened to resolve
to on that machine.

Fix (backend/conftest.py): a `TEST_REDIS_URL` module-level redirect
block, mirroring `TEST_DATABASE_URL`'s exactly — a complete no-op
unless the env var is set, and a hard safety gate (DB index must not
be 0 or 1) before it's ever allowed to redirect REDIS_URL. These tests
cover the pure validation logic unconditionally, and the actual
redirect-took-effect proof conditionally (skipped, not failed, when
TEST_REDIS_URL isn't set — the redirect is deliberately a no-op then,
so a plain `pytest app/` run must stay completely unaffected).
"""
import os

import pytest

from conftest import _validate_test_redis_url_db_index


def test_rejects_db_index_0():
    with pytest.raises(RuntimeError, match="must not be 0 or 1"):
        _validate_test_redis_url_db_index("redis://localhost:6379/0")


def test_rejects_missing_path_defaults_to_0_and_is_rejected():
    """No trailing /N at all — redis-py itself defaults this to DB 0,
    so the validator must treat a missing path exactly like an
    explicit '/0', not silently accept it as "unspecified, therefore
    fine"."""
    with pytest.raises(RuntimeError, match="must not be 0 or 1"):
        _validate_test_redis_url_db_index("redis://localhost:6379")


def test_rejects_db_index_1():
    """1 is rejected alongside 0 — the conventional second index a
    developer reaches for manually, not just the bare default."""
    with pytest.raises(RuntimeError, match="must not be 0 or 1"):
        _validate_test_redis_url_db_index("redis://localhost:6379/1")


def test_rejects_non_numeric_db_index():
    with pytest.raises(RuntimeError, match="numeric Redis DB index"):
        _validate_test_redis_url_db_index("redis://localhost:6379/not-a-number")


def test_accepts_an_isolated_db_index():
    assert _validate_test_redis_url_db_index("redis://localhost:6379/15") == 15


def test_redis_client_module_resolves_to_the_test_db_when_configured():
    """Proves the module-level redirect in conftest.py actually took
    effect for THIS test run — not merely that the validation logic
    above is correct in isolation. Skipped (not failed) when
    TEST_REDIS_URL isn't set, since the redirect is deliberately a
    no-op in that case (see conftest.py's own module docstring) — a
    plain `pytest app/` run must stay completely unaffected."""
    test_redis_url = os.environ.get("TEST_REDIS_URL")
    if not test_redis_url:
        pytest.skip("TEST_REDIS_URL not set — redirect is a no-op by design, nothing to prove here")

    from urllib.parse import urlparse

    from app.core.config import get_settings
    from app.core.redis_client import redis_client

    expected_db_index = int(urlparse(test_redis_url).path.lstrip("/"))
    assert get_settings().REDIS_URL == test_redis_url
    assert redis_client.connection_pool.connection_kwargs["db"] == expected_db_index
    assert redis_client.connection_pool.connection_kwargs["db"] not in (0, 1)

# A test that opens a real connection and exchanges commands with a
# live Redis server (via the `test_redis` fixture) belongs under
# tests/integration/ per this project's own convention — see
# tests/integration/test_sprint84_redis_test_isolation.py — not here,
# where every other test in this directory is a zero-dependency mock
# test that `pytest app/` must always run with no external service.
