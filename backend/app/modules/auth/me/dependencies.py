"""
FastAPI dependency wiring for GET /me — including the access-token
verification dependency itself, built on the NEW JWTService exclusively
(never imports core/security.py's decode_token, per "Do not integrate
with the old auth system"). This is the new track's equivalent of
auth/dependencies.py's get_current_user(), but reusable only by routers
in this isolated Sprint 3 track.
"""
import uuid

import jwt
from fastapi import Depends, Header
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import InvalidTokenException, UserNotFoundException
from app.db.session import get_db
from app.modules.auth.jwt.dependencies import get_jwt_service
from app.modules.auth.jwt.jwt_service import JWTService
from app.modules.auth.jwt.schemas import TokenType
from app.modules.auth.me.service import MeService
from app.modules.auth.repository import AuthRepository
from app.modules.users.models import User


def get_me_service() -> MeService:
    return MeService()


def get_current_user_v2(
    authorization: str | None = Header(default=None),
    jwt_service: JWTService = Depends(get_jwt_service),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise InvalidTokenException("Authorization header yo'q")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt_service.decode_token(token)
    except (jwt.PyJWTError, ValidationError):
        # Same compatibility gap handled in refresh/service.py: an
        # old-system token (no 'nbf' claim) or any malformed/expired/
        # tampered token must fail cleanly here, not with a raw 500.
        raise InvalidTokenException("Token yaroqsiz yoki eskirgan")

    if not jwt_service.verify_token_type(payload, TokenType.ACCESS):
        raise InvalidTokenException("Refresh token /me uchun ishlatilishi mumkin emas")

    repo = AuthRepository(db)
    user = repo.get_user_by_id(uuid.UUID(payload.sub))
    if user is None:
        raise UserNotFoundException("Foydalanuvchi topilmadi")
    return user
