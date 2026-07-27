"""Typed contracts for JWT payloads and issued token pairs."""
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenPayload(BaseModel):
    """Decoded, validated claims — decode_token() returns this instead of
    a raw dict, so callers get type-checked field access (payload.sub,
    not payload["sub"]) and can't typo a claim name."""
    sub: str
    jti: str
    type: TokenType
    iat: datetime
    nbf: datetime
    exp: datetime


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
