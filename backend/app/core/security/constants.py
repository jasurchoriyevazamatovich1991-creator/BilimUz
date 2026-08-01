"""
Security constants — password policy and JWT claim/type names.
FINAL, single source of truth as of Sprint 4 (Auth Cutover). The two
competing policies from Sprint 1 (12 chars) and Sprint 3 (10 chars) are
resolved here: 12 chars, per the Sprint 1 security-hardening decision.
"""
import re

# Password policy
PASSWORD_MIN_LENGTH = 12
UPPER_RE = re.compile(r"[A-Z]")
LOWER_RE = re.compile(r"[a-z]")
DIGIT_RE = re.compile(r"\d")
SPECIAL_RE = re.compile(r"[!@#$%^&*()\-_=+\[\]{};:,.<>/?]")

COMMON_WEAK_PASSWORDS = frozenset({
    "password123", "12345678901", "qwertyuiop12", "administrator1",
})

# Argon2 tuning
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 65536  # 64 MB
ARGON2_PARALLELISM = 4

# JWT token types and claim names
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"

CLAIM_SUBJECT = "sub"
CLAIM_JTI = "jti"
CLAIM_TYPE = "type"
CLAIM_ISSUED_AT = "iat"
CLAIM_NOT_BEFORE = "nbf"
CLAIM_EXPIRES_AT = "exp"

# Verification codes (registration/password-reset)
VERIFICATION_CODE_LENGTH = 6
VERIFICATION_CODE_MAX_ATTEMPTS = 5
