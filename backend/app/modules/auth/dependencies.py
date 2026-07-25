"""
FastAPI dependencies for auth: extracting/validating the bearer token and
enforcing role-based access. Imported by every other module's router
(that's why it lives in `auth`, not duplicated per-module).
"""
import uuid

import jwt
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.modules.auth.repository import AuthRepository
from app.db.session import get_db
from app.core.exceptions import InvalidTokenException, UserNotFoundException
from app.core.security import TokenType, decode_token
from app.modules.users.models import User


def get_auth_repository(db: Session = Depends(get_db)) -> AuthRepository:
    return AuthRepository(db)


def get_current_user(
    authorization: str | None = Header(default=None),
    repo: AuthRepository = Depends(get_auth_repository),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise InvalidTokenException("Authorization header yo'q")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise InvalidTokenException("Token yaroqsiz yoki eskirgan")

    if payload.get("type") != TokenType.ACCESS.value:
        raise InvalidTokenException("Access token talab qilinadi")

    user = repo.get_user_by_id(uuid.UUID(payload["sub"]))
    if user is None:
        raise UserNotFoundException("Foydalanuvchi topilmadi")
    return user


def require_roles(*allowed_role_names: str):
    """Usage: Depends(require_roles('Admin', 'Super Admin'))"""

    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role.name not in allowed_role_names:
            from app.core.exceptions import AppException
            from fastapi import status

            exc = AppException("Ruxsat yo'q")
            exc.status_code = status.HTTP_403_FORBIDDEN
            exc.error_code = "FORBIDDEN"
            raise exc
        return user

    return _check
