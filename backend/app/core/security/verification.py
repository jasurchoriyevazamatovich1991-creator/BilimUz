"""SMS/email verification-code helpers — unrelated to password/JWT
algorithm choice, carried over unchanged from the original core/security.py."""
import hashlib
import secrets

from app.core.config import get_settings
from app.core.security.constants import VERIFICATION_CODE_LENGTH

settings = get_settings()


def generate_verification_code() -> str:
    """6-digit numeric code, cryptographically random — not predictable."""
    return f"{secrets.randbelow(10 ** VERIFICATION_CODE_LENGTH):0{VERIFICATION_CODE_LENGTH}d}"


def hash_verification_code(code: str) -> str:
    """SHA-256 is enough here: codes are short-lived and rate-limited, unlike passwords."""
    return hashlib.sha256(f"{code}{settings.JWT_SECRET_KEY}".encode()).hexdigest()


def verify_verification_code(code: str, code_hash: str) -> bool:
    return secrets.compare_digest(hash_verification_code(code), code_hash)
