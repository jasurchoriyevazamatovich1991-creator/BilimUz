"""No magic numbers — every tunable security value lives here."""

# Password policy (Security Engineer spec: 12+ chars, mixed case, digit, special)
PASSWORD_MIN_LENGTH = 12
PASSWORD_HISTORY_SIZE = 5  # how many previous hashes are checked for reuse

# Rate limits: (max_requests, window_seconds)
LOGIN_RATE_LIMIT = (5, 60)
REGISTER_RATE_LIMIT = (3, 60)
VERIFY_RATE_LIMIT = (5, 60)

# Verification codes
VERIFICATION_CODE_LENGTH = 6
VERIFICATION_MAX_ATTEMPTS = 5

# A minimal denylist of common weak passwords — real deployments should
# check against a much larger breached-password corpus (e.g. HIBP range API).
COMMON_WEAK_PASSWORDS = frozenset({
    "password123", "12345678901", "qwertyuiop12", "administrator1",
})
