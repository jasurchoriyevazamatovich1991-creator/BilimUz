"""
Production-ready JWT issuance and verification using PyJWT. Stateless and
constructor-injected (secret/algorithm/expiry passed in, not read from
global settings inside the class) — makes it trivially unit-testable with
a throwaway secret, no monkeypatching of app.core.config needed.
"""
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.modules.auth.jwt.constants import ACCESS_TOKEN_TYPE, REFRESH_TOKEN_TYPE
from app.modules.auth.jwt.schemas import TokenPayload, TokenType


class JWTService:
    def __init__(self, secret_key: str, algorithm: str, access_expire_minutes: int, refresh_expire_days: int):
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._access_expire_minutes = access_expire_minutes
        self._refresh_expire_days = refresh_expire_days

    def create_access_token(self, subject: str) -> str:
        return self._create_token(
            subject, ACCESS_TOKEN_TYPE, timedelta(minutes=self._access_expire_minutes)
        )

    def create_refresh_token(self, subject: str) -> str:
        return self._create_token(
            subject, REFRESH_TOKEN_TYPE, timedelta(days=self._refresh_expire_days)
        )

    def decode_token(self, token: str) -> TokenPayload:
        """Raises jwt.PyJWTError (or a subclass, e.g. ExpiredSignatureError,
        InvalidSignatureError) on any invalid/expired/malformed token —
        callers handle it, this method doesn't swallow or reinterpret it."""
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
