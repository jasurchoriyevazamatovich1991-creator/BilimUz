"""
Production-ready password hashing and strength validation using Argon2
(the OWASP-recommended default over bcrypt for new systems — resistant
to GPU/ASIC cracking via tunable memory cost, not just time cost).
"""
from passlib.context import CryptContext

from app.modules.auth.security.constants import (
    ARGON2_MEMORY_COST,
    ARGON2_PARALLELISM,
    ARGON2_TIME_COST,
    DIGIT_RE,
    LOWER_RE,
    PASSWORD_MIN_LENGTH,
    SPECIAL_RE,
    UPPER_RE,
)
from app.modules.auth.security.schemas import PasswordValidationError, PasswordValidationResult


class PasswordService:
    """Stateless wrapper around passlib's Argon2 backend. No DB/repository
    dependency — safe to instantiate directly or inject via DI."""

    def __init__(self) -> None:
        self._context = CryptContext(
            schemes=["argon2"],
            deprecated="auto",
            argon2__time_cost=ARGON2_TIME_COST,
            argon2__memory_cost=ARGON2_MEMORY_COST,
            argon2__parallelism=ARGON2_PARALLELISM,
        )

    def hash_password(self, plain_password: str) -> str:
        return self._context.hash(plain_password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self._context.verify(plain_password, hashed_password)

    def validate_password_strength(self, password: str) -> PasswordValidationResult:
        """Collects every violated rule instead of raising on the first
        one — the caller (schema/router) decides how to present them."""
        errors: list[PasswordValidationError] = []

        if len(password) < PASSWORD_MIN_LENGTH:
            errors.append(PasswordValidationError(
                code="TOO_SHORT",
                message=f"Parol kamida {PASSWORD_MIN_LENGTH} belgidan iborat bo'lishi kerak",
            ))
        if not UPPER_RE.search(password):
            errors.append(PasswordValidationError(code="MISSING_UPPERCASE", message="Kamida bitta katta harf kerak"))
        if not LOWER_RE.search(password):
            errors.append(PasswordValidationError(code="MISSING_LOWERCASE", message="Kamida bitta kichik harf kerak"))
        if not DIGIT_RE.search(password):
            errors.append(PasswordValidationError(code="MISSING_DIGIT", message="Kamida bitta raqam kerak"))
        if not SPECIAL_RE.search(password):
            errors.append(PasswordValidationError(code="MISSING_SPECIAL_CHAR", message="Kamida bitta maxsus belgi kerak (!@#$%...)"))

        return PasswordValidationResult(is_valid=len(errors) == 0, errors=errors)
