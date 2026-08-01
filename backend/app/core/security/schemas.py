"""Typed contracts for password validation and JWT payloads/token pairs."""
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class PasswordValidationError(BaseModel):
    code: str
    message: str


class PasswordValidationResult(BaseModel):
    is_valid: bool
    errors: list[PasswordValidationError] = []


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenPayload(BaseModel):
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
