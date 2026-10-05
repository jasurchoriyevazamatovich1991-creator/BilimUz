"""No magic numbers — every tunable security value lives here.

Password policy constants moved to core/security/constants.py in
Sprint 4 (Auth Cutover) — single source of truth, no longer duplicated
here."""

PASSWORD_HISTORY_SIZE = 5  # how many previous hashes are checked for reuse

# Rate limits: (max_requests, window_seconds)
LOGIN_RATE_LIMIT = (5, 60)
REGISTER_RATE_LIMIT = (3, 60)
VERIFY_RATE_LIMIT = (5, 60)
# Sprint 73 — SEC-2. /auth/refresh and /auth/change-password were
# previously unprotected by any rate limit, unlike login/register/verify
# above — a brute-forceable gap (refresh-token guessing; change-password's
# current_password check accepts unlimited guesses). Limits set generous
# enough not to disrupt a legitimate user's normal session refresh cadence.
REFRESH_RATE_LIMIT = (20, 60)
CHANGE_PASSWORD_RATE_LIMIT = (5, 60)

# Verification codes
VERIFICATION_CODE_LENGTH = 6
VERIFICATION_MAX_ATTEMPTS = 5
