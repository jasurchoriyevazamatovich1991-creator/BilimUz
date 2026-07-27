"""Structured result type for password strength validation — returns ALL
violated rules at once, not just the first one, so a client can show a
complete checklist instead of a frustrating one-error-at-a-time loop."""
from pydantic import BaseModel


class PasswordValidationError(BaseModel):
    code: str
    message: str


class PasswordValidationResult(BaseModel):
    is_valid: bool
    errors: list[PasswordValidationError] = []
