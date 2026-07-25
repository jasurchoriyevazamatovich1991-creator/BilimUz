"""Single Redis client instance — used for rate limiting (and, later,
caching per docs/Roadmap v2.0). Sync client: our routes are sync (SQLAlchemy
Session), so an async client would gain nothing here."""
import redis

from app.core.config import get_settings

settings = get_settings()

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
