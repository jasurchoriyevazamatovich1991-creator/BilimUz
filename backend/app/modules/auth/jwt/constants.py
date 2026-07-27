"""
Token-type and claim-name constants. Secret key / algorithm / expiry
durations are NOT redefined here — they're pulled from app.core.config
(Settings) via constructor injection into JWTService, so there's exactly
one place (`.env` / Settings) that defines "how long is an access token
valid", not a second copy drifting out of sync.
"""

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"

# Claim names, spelled out once so a typo can't silently create a
# mismatched claim between create_*_token() and decode_token().
CLAIM_SUBJECT = "sub"
CLAIM_JTI = "jti"
CLAIM_TYPE = "type"
CLAIM_ISSUED_AT = "iat"
CLAIM_NOT_BEFORE = "nbf"
CLAIM_EXPIRES_AT = "exp"
