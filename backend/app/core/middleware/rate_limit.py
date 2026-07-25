"""
Fixed-window rate limiting via Redis INCR/EXPIRE. Applied as a FastAPI
dependency on specific endpoints (login, register, verify, password reset)
rather than globally — a nationwide platform's read-heavy public endpoints
(GET /subjects) must not share a budget with brute-forceable auth endpoints.

Both IP-based AND identifier-based (e.g. phone/email from the request body)
limiting are supported so an attacker can't defeat IP-limiting with a
botnet while still hammering one victim account.
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
