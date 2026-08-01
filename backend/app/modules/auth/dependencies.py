"""
FastAPI dependencies for auth: extracting/validating the bearer token and
enforcing role-based access. Imported by every other module's router
(that's why it lives in `auth`, not duplicated per-module).

Sprint 4 (Auth Cutover): uses the unified JWTService from core/security/
(typed TokenPayload, catches both jwt.PyJWTError and pydantic.ValidationError
— a real gap found and fixed during Sprint 3's isolated build, now the
permanent behavior here too).
"""
import uuid

import jwt
from fastapi import Depends, Header
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import InvalidTokenException, UserNotFoundException
from app.core.security.dependencies import get_jwt_service
from app.core.security.jwt_service import JWTService
from app.core.security.schemas import TokenType
from app.db.session import get_db
from app.modules.auth.repository import AuthRepository
from app.modules.users.models import User


def get_auth_repository(db: Session = Depends(get_db)) -> AuthRepository:
    return AuthRepository(db)


def get_current_user(
    authorization: str | None = Header(default=None),
    repo: AuthRepository = Depends(get_auth_repository),
    jwt_service: JWTService = Depends(get_jwt_service),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise InvalidTokenException("Authorization header yo'q")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt_service.decode_token(token)
    except (jwt.PyJWTError, ValidationError):
        raise InvalidTokenException("Token yaroqsiz yoki eskirgan")

    if not jwt_service.verify_token_type(payload, TokenType.ACCESS):
        raise InvalidTokenException("Access token talab qilinadi")

    user = repo.get_user_by_id(uuid.UUID(payload.sub))
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
