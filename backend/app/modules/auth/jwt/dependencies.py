"""
FastAPI dependency wiring for JWTService. Added now (not in Step 2)
because Step 2 had no router that needed to construct it via DI — this
is a pure addition, not a modification of anything Step 2 delivered.
"""
from functools import lru_cache

from app.core.config import get_settings
from app.modules.auth.jwt.jwt_service import JWTService


@lru_cache
def get_jwt_service() -> JWTService:
    settings = get_settings()
    return JWTService(
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        access_expire_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_expire_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
    )
