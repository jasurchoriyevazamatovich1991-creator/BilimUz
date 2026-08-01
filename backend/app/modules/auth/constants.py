"""No magic numbers — every tunable security value lives here.

Password policy constants moved to core/security/constants.py in
Sprint 4 (Auth Cutover) — single source of truth, no longer duplicated
here."""

PASSWORD_HISTORY_SIZE = 5  # how many previous hashes are checked for reuse

# Rate limits: (max_requests, window_seconds)
LOGIN_RATE_LIMIT = (5, 60)
REGISTER_RATE_LIMIT = (3, 60)
VERIFY_RATE_LIMIT = (5, 60)

# Verification codes
VERIFICATION_CODE_LENGTH = 6
VERIFICATION_MAX_ATTEMPTS = 5
