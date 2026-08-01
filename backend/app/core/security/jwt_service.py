"""
JWT issuance and verification (PyJWT). This is now THE JWT implementation
for the whole platform — Sprint 3's isolated version replaces Sprint 1's
original functions (Sprint 4 Auth Cutover). Adds the 'nbf' claim, which
the original implementation lacked.
"""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.security.constants import ACCESS_TOKEN_TYPE, REFRESH_TOKEN_TYPE
from app.core.security.schemas import TokenPayload, TokenType


class JWTService:
    def __init__(self, secret_key: str, algorithm: str, access_expire_minutes: int, refresh_expire_days: int):
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._access_expire_minutes = access_expire_minutes
        self._refresh_expire_days = refresh_expire_days

    def create_access_token(self, subject: str) -> str:
        return self._create_token(subject, ACCESS_TOKEN_TYPE, timedelta(minutes=self._access_expire_minutes))

    def create_refresh_token(self, subject: str) -> str:
        return self._create_token(subject, REFRESH_TOKEN_TYPE, timedelta(days=self._refresh_expire_days))

    def decode_token(self, token: str) -> TokenPayload:
        """Raises jwt.PyJWTError on invalid/expired/malformed tokens, and
        pydantic.ValidationError if the claims don't match TokenPayload's
        shape — callers must catch both (see auth/dependencies.py)."""
        raw = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
        return TokenPayload(**raw)

    def verify_token_type(self, payload: TokenPayload, expected_type: TokenType) -> bool:
        return payload.type == expected_type

    def _create_token(self, subject: str, token_type: str, expires_delta: timedelta) -> str:
        now = datetime.now(timezone.utc)
        claims = {
            "sub": subject,
            "jti": str(uuid.uuid4()),
            "type": token_type,
            "iat": now,
            "nbf": now,
            "exp": now + expires_delta,
        }
        return jwt.encode(claims, self._secret_key, algorithm=self._algorithm)


def hash_refresh_token(token: str) -> str:
    """Refresh tokens are stored hashed — a DB leak alone must not grant access."""
    return hashlib.sha256(token.encode()).hexdigest()
