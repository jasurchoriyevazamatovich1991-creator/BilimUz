"""
Sprint 40 — Real PostgreSQL Integration Test Infrastructure.

CRITICAL DESIGN CONSTRAINT (see the module-level block below):
`app/db/database.py`'s `engine` is created at IMPORT time, bound to
whatever `settings.DATABASE_URL` resolves to at that instant. Since
pytest always loads every `conftest.py` before it collects/imports any
test module, this file is the ONLY safe place to redirect
`DATABASE_URL` to the test database BEFORE that engine (or anything
that transitively imports it) can ever be constructed with the wrong
URL.

SAFETY GUARANTEE FOR THE EXISTING 483 MOCK-BASED TESTS:
None of them import `app.db.database`, `app.db.session`, or `app.main`
(verified directly — `grep -rln "SessionLocal|get_db" app --include
test_*.py` returns nothing). The block below is a complete no-op
unless `TEST_DATABASE_URL` is set in the environment, so running the
existing suite exactly as before (`pytest app/ scripts/`, no env var)
is entirely unaffected by this file's existence.
"""
import os

# =====================================================================
# Requirement 1 — TEST_DATABASE_URL, never auto-derived from DATABASE_URL.
# Requirement 3 — must run before any `app.*` import. Runs unconditionally
# at conftest.py's own module load (the earliest pytest hook available),
# but only ACTS when TEST_DATABASE_URL is actually present — so it never
# touches global environment for a run that isn't requesting integration
# tests at all.
# =====================================================================
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

if TEST_DATABASE_URL:
    # Requirement 2 — hard safety gate: refuse anything that isn't
    # obviously a throwaway test database, checked BEFORE this value is
    # ever assigned to DATABASE_URL (i.e. before it could reach the real
    # engine). "ends with _test" is deliberately strict and literal —
    # not a heuristic — matching the brief's own exact wording.
    _db_name = TEST_DATABASE_URL.rstrip("/").rsplit("/", 1)[-1].split("?")[0]
    if not _db_name.endswith("_test"):
        raise RuntimeError(
            f"TEST_DATABASE_URL's database name must end with '_test' — got "
            f"{_db_name!r} (from TEST_DATABASE_URL). Refusing to start: this "
            f"check exists specifically so integration tests can never be "
            f"pointed at a real development/production database."
        )
    # Only NOW, after the safety gate passes, is DATABASE_URL redirected —
    # before any `app.*` import happens anywhere in this test run.
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL


import pytest  # noqa: E402 — after the safety gate above, deliberately
from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402


def _require_test_database_url() -> str:
    """Requirement 1 — a clear, explicit failure (not a silent skip, not
    a fallback to DATABASE_URL) for any test that actually requests a
    real-database fixture without TEST_DATABASE_URL set."""
    if not TEST_DATABASE_URL:
        pytest.fail(
            "TEST_DATABASE_URL environment variable is required for "
            "integration tests. Example:\n"
            "  TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/bilimuz_test "
            "pytest app/modules/lessons/tests/test_lesson_order_integration.py\n"
            "(Tests that don't request the pg_session/client fixtures are "
            "completely unaffected by this and continue to run as before.)",
            pytrace=False,
        )
    return TEST_DATABASE_URL  # pragma: no cover — pytest.fail always raises above


def _run_alembic_upgrade_to_head(db_url: str) -> None:
    """Requirement 4 — applies the EXISTING, unmodified 0001->0010 chain.
    Does not touch alembic/env.py: env.py already reads
    `settings.DATABASE_URL`, which is DATABASE_URL == TEST_DATABASE_URL by
    the time this runs (set at module load, above) — so this is exactly
    the same code path `alembic upgrade head` takes from the CLI, just
    invoked programmatically instead of via subprocess."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parent
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def pg_test_database() -> str:
    """
    Session-scoped: runs once per test session.

    1. Validates TEST_DATABASE_URL is set (fails clearly if not).
    2. Creates the test database ONLY if it doesn't already exist
       (Requirement 2 — "CREATE DATABASE faqat mavjud bo'lmagan holatda
       bajarilsin"). Never drops or recreates an existing test database.
    3. Applies the existing 0001->0010 migration chain to it.

    Connects ONLY to the database named in TEST_DATABASE_URL (already
    validated above to end in "_test") for both the admin
    (CREATE DATABASE) step and the migration step — the development/
    production `bilimuz` database is never touched by this fixture.
    """
    from sqlalchemy import create_engine

    db_url = _require_test_database_url()
    url = make_url(db_url)
    db_name = url.database

    # CREATE DATABASE has no native "IF NOT EXISTS" in PostgreSQL, so
    # check pg_database first — this is what makes step 2 idempotent
    # across repeated test runs without ever dropping existing data.
    admin_url = url.set(database="postgres")
    admin_engine = create_engine(admin_url.render_as_string(hide_password=False), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}
            ).scalar()
            if not exists:
                # Identifier-quoted, not a bound parameter — CREATE DATABASE
                # doesn't support parameter binding for the DB name, but
                # db_name here is only ever derived from TEST_DATABASE_URL,
                # which the caller controls (same trust level as
                # DATABASE_URL itself already has throughout this codebase).
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        admin_engine.dispose()

    _run_alembic_upgrade_to_head(db_url)
    return db_url


@pytest.fixture(scope="function")
def pg_session(pg_test_database):
    """
    Function-scoped: one real PostgreSQL session per test, wrapped in an
    outer transaction that is ALWAYS rolled back when the test ends —
    this is what gives every test full isolation from every other test
    WITHOUT dropping/recreating the schema between tests (Phase 3's
    explicit requirement: "Schema test sessionlar orasida qayta-qayta
    yaratilib/o'chirilmasin").

    Uses the standard SQLAlchemy "join a session into an external
    transaction" pattern with a nested transaction/savepoint, so that
    application code under test calling `session.commit()` (which every
    existing service in this codebase does) only ends the INNER
    (savepoint) transaction — the outer transaction, and therefore the
    rollback that undoes everything at the end of the test, is
    unaffected either way.
    """
    from app.db.database import engine  # imported here, not at module top — only after DATABASE_URL is guaranteed to be the test URL

    connection = engine.connect()
    outer_transaction = connection.begin()

    # `join_transaction_mode="create_savepoint"` (SQLAlchemy 2.0.20+,
    # this project pins 2.0.35) is the official, built-in replacement for
    # the older hand-rolled `event.listens_for(after_transaction_end)`
    # savepoint-recreation recipe — that older pattern does not reliably
    # survive a service-layer `session.commit()` (every existing service
    # in this codebase calls `self.repo.commit()`), which was observed
    # directly here as a "transaction already deassociated from
    # connection" warning and a broken rollback. This built-in mode
    # keeps the OUTER transaction (and therefore the rollback below)
    # intact no matter how many times application code under test calls
    # commit() on the session.
    session = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")()

    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def client(pg_session):
    """
    FastAPI TestClient with `get_db` overridden to yield the SAME
    `pg_session` the test itself uses — so an HTTP call made through this
    client and a direct DB assertion in the test see the exact same
    (not-yet-committed-to-the-real-table, rolled-back-at-teardown) data.

    Wraps the app in a tiny ASGI middleware (defined only here, in
    conftest.py — app/main.py is never modified) that overrides
    scope["client"] with a real-looking IP before delegating to the
    real app. Starlette's own TestClient hardcodes
    scope["client"] = ["testclient", 50000] with no way to change it,
    which real PostgreSQL correctly rejects for the INET-typed
    refresh_tokens.ip_address/login_history.ip_address columns — a
    check that never fires against MagicMock. Production servers always
    see a real client IP regardless; this is purely a test-environment
    accommodation.
    """
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import app

    def _override_get_db():
        yield pg_session

    class _RealClientIPASGIWrapper:
        """Delegates everything to the real app, only replacing the
        fake test-transport client tuple with a real-looking IP. Each
        client fixture instance gets its OWN random IP (not just a
        fixed one) — rate_limit's Redis key is keyed only by
        request.client.host (see core/middleware/rate_limit.py), and
        unlike pg_session, Redis state is never rolled back between
        tests. Reusing one fixed fake IP across every test in this file
        would make them all share one rate-limit budget and eventually
        trip a real 429 — a test-isolation artifact, not a production
        bug (real users always have distinct IPs)."""

        def __init__(self, wrapped_app, fake_ip: str):
            self._app = wrapped_app
            self._fake_ip = fake_ip

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                scope = dict(scope)
                scope["client"] = (self._fake_ip, 12345)
            await self._app(scope, receive, send)

    import random

    fake_ip = f"127.{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}"
    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(_RealClientIPASGIWrapper(app, fake_ip)) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
