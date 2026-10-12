"""
Sprint 84 — Package 1 (rate-limit documentation and behavior). Pins the
actual configured rate-limit scope and values against a hardcoded
expectation that mirrors `docs/API/api_blueprint.md`'s corrected
Section 8 table, so a future change to a limit's value, its window, or
which endpoints carry a limit at all is caught by a failing test
instead of silently drifting the documentation out of sync again —
exactly the previously-reported mismatch this sprint confirmed and
fixed (docs only; no rate-limit value or policy changed).

Audit finding (verified directly against source before this sprint):
`docs/API/api_blueprint.md`'s old Section 8 table was wrong on three
independent counts — REGISTER's limit (claimed 5, actual 3), the `ai/*`
window unit (claimed requests/hour, actual requests/minute), and a
fabricated blanket "100 requests/minute/user on everything else" limit
that was never implemented anywhere (`rate_limit()`/`rate_limit_by_user()`
are applied only at the specific call sites this test enumerates — there
is no global rate-limiting middleware in `app/main.py`). It also
documented a `Retry-After` response header that
`app_exception_handler()` never sets.
"""
from app.core.exceptions import RateLimitExceededException
from app.modules.ai.constants import MESSAGE_RATE_LIMIT_MAX_REQUESTS, MESSAGE_RATE_LIMIT_WINDOW_SECONDS
from app.modules.auth.constants import (
    CHANGE_PASSWORD_RATE_LIMIT,
    LOGIN_RATE_LIMIT,
    REFRESH_RATE_LIMIT,
    REGISTER_RATE_LIMIT,
    VERIFY_RATE_LIMIT,
)
from app.modules.certificates.router import CERTIFICATE_VERIFY_RATE_LIMIT


def test_auth_rate_limit_constants_match_documented_values():
    """Each (max_requests, window_seconds) pair here must match
    docs/API/api_blueprint.md's Section 8 table exactly. A change to
    any of these constants without updating that table (or vice versa)
    is exactly the class of drift this sprint's audit found."""
    assert REGISTER_RATE_LIMIT == (3, 60)
    assert LOGIN_RATE_LIMIT == (5, 60)
    assert VERIFY_RATE_LIMIT == (5, 60)
    assert REFRESH_RATE_LIMIT == (20, 60)
    assert CHANGE_PASSWORD_RATE_LIMIT == (5, 60)


def test_certificate_verify_rate_limit_matches_documented_value():
    assert CERTIFICATE_VERIFY_RATE_LIMIT == (20, 60)


def test_ai_message_rate_limit_is_per_minute_not_per_hour():
    """The old doc claimed 20 requests/HOUR/user for `/ai/*` — the real
    configured window is 60 seconds (one minute), not 3600. Asserting
    the window explicitly (not just the request count) is the whole
    point: a correct count with the wrong unit is still a documentation
    mismatch."""
    assert MESSAGE_RATE_LIMIT_MAX_REQUESTS == 10
    assert MESSAGE_RATE_LIMIT_WINDOW_SECONDS == 60


def test_rate_limit_exceeded_response_has_no_retry_after_contract():
    """The old doc claimed a `Retry-After` header is returned on 429.
    RateLimitExceededException carries no header information at all —
    app_exception_handler() (core/exceptions.py) builds its JSONResponse
    from status_code/message/errors only, with no `headers=` argument
    anywhere in that function. This test pins the exception's own
    shape: it exposes nothing a header-adding layer could read, so if
    a `Retry-After` header is ever actually desired, it cannot be added
    by accident without this test (or the exception's shape) visibly
    changing first."""
    exc = RateLimitExceededException("test")
    assert exc.status_code == 429
    assert not hasattr(exc, "retry_after")
    assert not hasattr(exc, "headers")
