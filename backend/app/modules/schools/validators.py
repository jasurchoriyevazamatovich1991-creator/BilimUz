"""
Pure validation functions — no I/O, reusable from schemas or services.

phone validation is defined locally (NOT imported from
app.modules.auth.validators) to keep this module's cross-module
dependency count at zero, per the approved architecture
(docs/Sprint10_Schools_LearningCenters_Architecture.md) — even though
the resulting pattern is the same broad E.164 `+998` + 9-digit format,
unrestricted by mobile-operator prefix (approved decision 2: accepts
both mobile and landline institutional numbers).
"""
import re

from app.modules.schools.constants import MAX_NAME_LENGTH, MIN_NAME_LENGTH

_UZ_PHONE_RE = re.compile(r"^\+998\d{9}$")


def validate_school_name(name: str) -> str:
    stripped = name.strip()
    if not (MIN_NAME_LENGTH <= len(stripped) <= MAX_NAME_LENGTH):
        raise ValueError(f"Maktab nomi {MIN_NAME_LENGTH}-{MAX_NAME_LENGTH} belgidan iborat bo'lishi kerak")
    return stripped


def validate_institutional_phone(phone: str | None) -> str | None:
    """Broader than a mobile-only pattern by design — accepts both
    mobile and landline +998 numbers (approved decision 2)."""
    if phone is None:
        return None
    if not _UZ_PHONE_RE.match(phone):
        raise ValueError("Telefon raqam +998XXXXXXXXX formatida bo'lishi kerak")
    return phone
