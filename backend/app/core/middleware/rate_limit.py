"""
Fixed-window rate limiting via Redis INCR/EXPIRE. Applied as a FastAPI
dependency on specific endpoints (login, register, verify, refresh,
change-password, certificate verification) rather than globally — a
nationwide platform's read-heavy public endpoints (GET /subjects) must
not share a budget with brute-forceable auth endpoints.

Sprint 84 — Package 1 correction. This docstring previously claimed
"Both IP-based AND identifier-based (e.g. phone/email from the request
body) limiting are supported" — verified against the actual
`_dependency()` body below and every call site (auth/router.py,
certificates/router.py): that was never true. `key` is built from
`request.client.host` ONLY; no call site passes, and `rate_limit()`
has never accepted, a request-body identifier (phone/email) at all.
This is the exact, already-correctly-flagged "Known deviation" in
`app/modules/auth/README.md`'s own Security notes section — an
attacker who defeats the IP limit with a botnet can still hammer one
victim account's `/login` without tripping this limiter. That
deviation is a documented, deliberate scope decision (see that
README's "Future improvements" section), not something this sprint
invents a fix for — correcting this docstring to match the verified,
already-accurately-documented behavior elsewhere is the only change
made here.

A separate, user-keyed limiter — `rate_limit_by_user()` in
`app/modules/auth/dependencies.py` — exists for the one endpoint that
needs to key on an authenticated user instead of IP (the `ai` module's
message-send limit). It is a distinct function with its own key
scheme, not a mode of this one, and does not make this function
identifier-aware.
"""
from fastapi import Request

from app.core.exceptions import RateLimitExceededException
from app.core.redis_client import redis_client


def rate_limit(key_prefix: str, max_requests: int, window_seconds: int):
    """Usage: Depends(rate_limit('login', max_requests=5, window_seconds=60))"""

    def _dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{key_prefix}:{ip}"
        current = redis_client.incr(key)
        if current == 1:
            redis_client.expire(key, window_seconds)
        if current > max_requests:
            raise RateLimitExceededException(
                "Juda ko'p urinish qilindi. Iltimos, birozdan so'ng qayta urining."
            )

    return _dependency
