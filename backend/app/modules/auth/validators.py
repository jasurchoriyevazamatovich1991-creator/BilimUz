"""
Pure validation functions — no I/O, no DB, no HTTP. Called from Pydantic
schemas (field_validator) and reusable anywhere else (e.g. AI module input).

Sprint 4 (Auth Cutover): validate_password_strength() now delegates to the
unified core.security.password_service.PasswordService instead of
duplicating regex checks here — single source of truth for the password
policy (12 chars, per core/security/constants.py).
"""
import re

from app.core.security.password_service import PasswordService

_UZ_PHONE_RE = re.compile(r"^\+998\d{9}$")
_password_service = PasswordService()  # stateless — a module-level instance is safe


def validate_uzbek_phone(phone: str) -> str:
    if not _UZ_PHONE_RE.match(phone):
        raise ValueError("Telefon raqam +998XXXXXXXXX formatida bo'lishi kerak")
    return phone


def validate_password_strength(password: str) -> str:
    """Pydantic field_validator adapter: PasswordService returns ALL
    violated rules; this raises ValueError with them joined, since
    Pydantic's field_validator protocol expects a single exception."""
    result = _password_service.validate_password_strength(password)
    if not result.is_valid:
        raise ValueError("; ".join(e.message for e in result.errors))
    return password


def validate_verification_code_format(code: str) -> bool:
    return code.isdigit() and len(code) == 6
