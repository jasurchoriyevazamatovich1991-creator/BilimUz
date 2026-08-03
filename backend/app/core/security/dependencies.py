"""FastAPI dependency wiring for PasswordService, JWTService, and
EncryptionService (Sprint 8) — all stateless, so cached singletons are safe."""
from functools import lru_cache

from app.core.config import get_settings
from app.core.security.encryption import EncryptionService
from app.core.security.jwt_service import JWTService
from app.core.security.password_service import PasswordService


@lru_cache
def get_password_service() -> PasswordService:
    return PasswordService()


@lru_cache
def get_jwt_service() -> JWTService:
    settings = get_settings()
    return JWTService(
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        access_expire_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_expire_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
    )


@lru_cache
def get_encryption_service() -> EncryptionService:
    return EncryptionService()
