"""
Sprint 84 — Package 3 (OpenAPI contract validation). Confirms the
application's actual OpenAPI schema can be generated and is valid,
serializable JSON — the exact gap this sprint's audit found: no test
or CI check anywhere in this repository ever called `app.openapi()`
or hit `/api/v1/openapi.json` (confirmed by a repo-wide search before
this change), so a router registration mistake, a schema-breaking
Pydantic model, or a duplicate operation ID could land without any
automated signal — until someone happened to open `/docs` by hand.

Deliberately needs no live PostgreSQL or Redis: importing `app.main`
only constructs a lazy, unconnected SQLAlchemy engine and a lazy,
unconnected Redis client (neither opens a real connection at import
time — confirmed directly in this sandbox with both services stopped,
the same fact app/core/tests/test_startup_secret_validation.py's own
module docstring already documents), and `app.openapi()` is pure route/
Pydantic-model introspection — it never touches a database or cache.
It also never triggers `app.main`'s `@app.on_event("startup")` handler
(that only fires through a real ASGI lifespan, e.g. via
`TestClient(app)` used as a context manager, which this test
deliberately does not use), so no `ENVIRONMENT`-gated startup check
runs here either — only the already-required `.env`/`ENVIRONMENT`
value `Settings()` needs just to construct.
"""
import json

from app.main import app


def test_openapi_schema_generates_without_error():
    """The actual regression this sprint's audit found missing: nothing
    previously called this at all."""
    schema = app.openapi()
    assert isinstance(schema, dict)


def test_openapi_schema_has_the_expected_top_level_shape():
    schema = app.openapi()
    assert "openapi" in schema
    assert "info" in schema
    assert "paths" in schema
    assert schema["info"]["title"] == app.title


def test_openapi_schema_is_json_serializable():
    """FastAPI serves this exact object as JSON at
    `{API_V1_PREFIX}/openapi.json` — if it contained anything
    `json.dumps` can't handle, the real endpoint would 500 for every
    caller (Swagger UI included), not just fail a test."""
    schema = app.openapi()
    serialized = json.dumps(schema)
    assert isinstance(serialized, str)
    assert len(serialized) > 0


def test_openapi_schema_registers_known_auth_endpoints():
    """A coarse but real regression guard: if the auth router (or any
    router included in app/api/router.py) silently failed to register —
    a wrong prefix, an import error swallowed somewhere, a duplicate
    path — this is the kind of break that would otherwise only surface
    by someone noticing a 404 that used to be a 200."""
    from app.core.config import get_settings

    schema = app.openapi()
    prefix = get_settings().API_V1_PREFIX
    assert f"{prefix}/auth/login" in schema["paths"]
    assert f"{prefix}/auth/register" in schema["paths"]


def test_openapi_url_matches_the_configured_api_prefix():
    from app.core.config import get_settings

    assert app.openapi_url == f"{get_settings().API_V1_PREFIX}/openapi.json"
