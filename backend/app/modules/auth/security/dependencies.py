"""FastAPI dependency wiring for PasswordService — stateless, so a single
shared instance is safe (no per-request DB session needed, unlike the
repository-backed services elsewhere in the codebase)."""
from functools import lru_cache

from app.modules.auth.security.password_service import PasswordService


@lru_cache
def get_password_service() -> PasswordService:
    return PasswordService()
