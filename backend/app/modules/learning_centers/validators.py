"""
Pure validation functions — no I/O, reusable from schemas or services.

phone validation is defined locally (not imported from
app.modules.schools.validators or app.modules.auth.validators) to keep
this module's cross-module dependency count at zero, matching schools'
identical design choice — the two modules are structurally close but
deliberately not sharing code, per the module-independence precedent
already established by grades/topics/lessons.
"""
import re

from app.modules.learning_centers.constants import (
    MAX_NAME_LENGTH,
    MAX_OWNER_NAME_LENGTH,
    MIN_NAME_LENGTH,
    MIN_OWNER_NAME_LENGTH,
)

_UZ_PHONE_RE = re.compile(r"^\+998\d{9}$")


def validate_center_name(name: str) -> str:
    stripped = name.strip()
    if not (MIN_NAME_LENGTH <= len(stripped) <= MAX_NAME_LENGTH):
        raise ValueError(f"O'quv markazi nomi {MIN_NAME_LENGTH}-{MAX_NAME_LENGTH} belgidan iborat bo'lishi kerak")
    return stripped


def validate_owner_name(owner_name: str | None) -> str | None:
    if owner_name is None:
        return None
    stripped = owner_name.strip()
    if not (MIN_OWNER_NAME_LENGTH <= len(stripped) <= MAX_OWNER_NAME_LENGTH):
        raise ValueError(f"Egasi ismi {MIN_OWNER_NAME_LENGTH}-{MAX_OWNER_NAME_LENGTH} belgidan iborat bo'lishi kerak")
    return stripped


def validate_institutional_phone(phone: str | None) -> str | None:
    """Broader than a mobile-only pattern by design — accepts both
    mobile and landline +998 numbers (approved decision 2)."""
    if phone is None:
        return None
    if not _UZ_PHONE_RE.match(phone):
        raise ValueError("Telefon raqam +998XXXXXXXXX formatida bo'lishi kerak")
    return phone
