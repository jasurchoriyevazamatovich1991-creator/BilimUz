"""
Password hashing and JWT issuance/verification.
This is the ONLY module allowed to touch bcrypt or the JWT secret directly —
every other module calls these functions instead of reimplementing crypto.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from enum import StrEnum

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.BCRYPT_ROUNDS)


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def create_token(subject: uuid.UUID, token_type: TokenType, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),  # unique id — enables refresh-token revocation
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: uuid.UUID) -> str:
    return create_token(
        user_id, TokenType.ACCESS, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )


def create_refresh_token(user_id: uuid.UUID) -> str:
    return create_token(
        user_id, TokenType.REFRESH, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )


def decode_token(token: str) -> dict:
    """Raises jwt.PyJWTError on invalid/expired token — caller must handle it."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def generate_verification_code() -> str:
    """6-digit numeric code, cryptographically random — not predictable."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_verification_code(code: str) -> str:
    """SHA-256 is enough here: codes are short-lived and rate-limited, unlike passwords."""
    return hashlib.sha256(f"{code}{settings.JWT_SECRET_KEY}".encode()).hexdigest()


def verify_verification_code(code: str, code_hash: str) -> bool:
    return secrets.compare_digest(hash_verification_code(code), code_hash)


def hash_refresh_token(token: str) -> str:
    """Refresh tokens are stored hashed — DB leak alone must not grant access."""
    return hashlib.sha256(token.encode()).hexdigest()
