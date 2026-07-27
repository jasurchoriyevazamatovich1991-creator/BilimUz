"""
Business logic for the isolated Refresh Token API. Uses the NEW
JWTService exclusively for token creation/decoding/type-checking — never
touches core/security.py's JWT functions ("Do not integrate with the old
JWT system"). Reuses the EXISTING AuthRepository for storage (same
refresh_tokens table, same get_by_jti/revoke/create pattern already used
by the old system and by Steps 3-4) — that's data-layer reuse, not
JWT-system integration, and required zero new repository methods.

Rotation is always-on (not optional): the old refresh token is revoked
the instant a new pair is issued, exactly matching the existing system's
security posture (a stolen, already-used refresh token becomes worthless
immediately) — "optionally rotate" in the spec is interpreted as "this
endpoint may rotate," and always-rotate is the secure default, not a
toggle exposed to the caller.
"""
import uuid

import jwt
from pydantic import ValidationError

from app.core.exceptions import InvalidTokenException
from app.core.security import hash_refresh_token
from app.modules.auth.jwt.jwt_service import JWTService
from app.modules.auth.jwt.schemas import TokenPayload, TokenType
from app.modules.auth.models import RefreshToken
from app.modules.auth.refresh.schemas import RefreshTokenResponse
from app.modules.auth.repository import AuthRepository


class RefreshService:
    def __init__(self, repository: AuthRepository, jwt_service: JWTService):
        self.repo = repository
        self.jwt_service = jwt_service

    def refresh(self, refresh_token: str) -> RefreshTokenResponse:
        payload = self._decode_or_reject(refresh_token)

        if not self.jwt_service.verify_token_type(payload, TokenType.REFRESH):
            raise InvalidTokenException("Access token refresh o'rniga ishlatilishi mumkin emas")

        stored = self.repo.get_refresh_token_by_jti(payload.jti)
        if stored is None or stored.token_hash != hash_refresh_token(refresh_token):
            raise InvalidTokenException("Token bekor qilingan yoki topilmadi")

        self.repo.revoke_refresh_token(stored)  # rotation: old token is single-use
        response = self._issue_tokens(uuid.UUID(payload.sub))
        self.repo.commit()
        return response

    def _decode_or_reject(self, token: str) -> TokenPayload:
        """Catches BOTH jwt.PyJWTError (expired/tampered/malformed token)
        AND pydantic.ValidationError (a structurally different token —
        e.g. one issued by the old system, missing the 'nbf' claim this
        module's TokenPayload requires) — either way, the caller gets a
        clean 401, never a raw 500."""
        try:
            return self.jwt_service.decode_token(token)
        except (jwt.PyJWTError, ValidationError):
            raise InvalidTokenException("Refresh token yaroqsiz yoki eskirgan")

    def _issue_tokens(self, user_id: uuid.UUID) -> RefreshTokenResponse:
        access = self.jwt_service.create_access_token(subject=str(user_id))
        refresh = self.jwt_service.create_refresh_token(subject=str(user_id))
        access_payload = self.jwt_service.decode_token(access)
        refresh_payload = self.jwt_service.decode_token(refresh)

        self.repo.create_refresh_token(
            RefreshToken(user_id=user_id, token_hash=hash_refresh_token(refresh), jti=refresh_payload.jti)
        )

        return RefreshTokenResponse(
            access_token=access,
            refresh_token=refresh,
            access_token_expires_in=int((access_payload.exp - access_payload.iat).total_seconds()),
            access_token_expires_at=access_payload.exp,
            refresh_token_expires_in=int((refresh_payload.exp - refresh_payload.iat).total_seconds()),
            refresh_token_expires_at=refresh_payload.exp,
        )
