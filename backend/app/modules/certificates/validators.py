"""Pure functions — no I/O. Certificate number / verification code
generation live here so they're unit-testable in isolation."""
import secrets
import string
from datetime import datetime, timezone

from app.modules.certificates.constants import (
    CERTIFICATE_NUMBER_PREFIX,
    MAX_TEMPLATE_NAME_LENGTH,
    MIN_TEMPLATE_NAME_LENGTH,
    VERIFICATION_CODE_LENGTH,
)


def generate_certificate_number() -> str:
    """Human-readable, e.g. BILIMUZ-2026-A1B2C3D4 — distinct from the
    verification_code by design (see certificates/README.md)."""
    year = datetime.now(timezone.utc).year
    suffix = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    return f"{CERTIFICATE_NUMBER_PREFIX}-{year}-{suffix}"


def generate_verification_code() -> str:
    """Shorter, separate code for the public verification lookup — never
    the same value as certificate_number (see README 'Business rules')."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(VERIFICATION_CODE_LENGTH))


def validate_template_name(name: str) -> str:
    stripped = name.strip()
    if not (MIN_TEMPLATE_NAME_LENGTH <= len(stripped) <= MAX_TEMPLATE_NAME_LENGTH):
        raise ValueError(f"Shablon nomi {MIN_TEMPLATE_NAME_LENGTH}-{MAX_TEMPLATE_NAME_LENGTH} belgidan iborat bo'lishi kerak")
    return stripped
