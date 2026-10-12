"""
Sprint 84 — Package 2 (Redis test isolation), against a real Redis
server. Lives under tests/integration/ per this project's own
convention (see root README's folder structure: "tests/integration/ —
real PostgreSQL talab qiluvchi testlar" — the same separation applies
to any test needing a real external service, Redis included), unlike
the pure validation-logic tests in
app/core/tests/test_redis_test_isolation.py, which need no live
connection and always run as part of the zero-dependency mock suite.

Requires TEST_REDIS_URL to be set (see backend/conftest.py's
module-level redirect block) — fails clearly via the `test_redis`
fixture's own _require_test_redis_url() call if it isn't, exactly like
any pg_session-based integration test already fails clearly without
TEST_DATABASE_URL.
"""


def test_redis_fixture_is_isolated_and_flushed_at_teardown(test_redis):
    """Round-trips a real key against the isolated test Redis database
    and confirms it is not DB 0/1 — the two indexes the safety gate in
    conftest.py's module-level block refuses to redirect to."""
    test_redis.set("sprint84_isolation_probe", "1")
    assert test_redis.get("sprint84_isolation_probe") == "1"
    assert test_redis.connection_pool.connection_kwargs["db"] not in (0, 1)


def test_rate_limit_dependency_writes_into_the_isolated_test_db_not_db_zero(test_redis):
    """The real regression this package closes: exercising the actual
    `rate_limit()` dependency (the same one every auth endpoint uses)
    must write its `ratelimit:*` key into the isolated TEST_REDIS_URL
    database — the one `test_redis` is connected to and flushes at
    teardown — not into DB 0/1, which this fixture never touches."""
    from app.core.middleware.rate_limit import rate_limit

    class _FakeClient:
        host = "198.51.100.42"

    class _FakeRequest:
        client = _FakeClient()

    dependency = rate_limit("sprint84_isolation_check", max_requests=100, window_seconds=60)
    dependency(_FakeRequest())

    # If app.core.redis_client.redis_client were still pointed at a
    # different database than TEST_REDIS_URL, this key would not be
    # visible through test_redis (a separate connection to the
    # isolated DB) — proving the redirect actually took effect for the
    # dependency's own real code path, not just for a client this test
    # constructed itself.
    assert test_redis.get("ratelimit:sprint84_isolation_check:198.51.100.42") == "1"
