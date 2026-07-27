# Login Module — `app/modules/auth/login/`

Sprint 3, Step 4: Login API using `PasswordService` (Argon2) and `JWTService`.

## Endpoint

```
POST /api/v1/auth/login-v2
```

**Deliberately NOT `/api/v1/auth/login`** — same reasoning as Step 3's `/auth/registration`: the existing login endpoint in `app/modules/auth/router.py` is completely untouched. `-v2` signals "parallel implementation, cutover not yet decided" — not "this supersedes the old one," which remains a deliberate future decision (see `auth/registration/README.md`'s cutover note, which applies here too).

## What it does

1. Looks up the user **by email only** (per this step's requirement) via the existing, unmodified `AuthRepository.get_user_by_identifier`.
2. Verifies the password with `PasswordService.verify_password()` (Argon2).
3. Issues an access + refresh token pair via `JWTService`, persists the hashed refresh token (existing `AuthRepository.create_refresh_token`, same as Step 3).
4. Records login history and an audit log entry (`auth.login_success`) — reusing existing infrastructure (`core/audit.py`, `AuthRepository.record_login`), not reimplementing it.
5. Returns access token, refresh token, token type, **and explicit expiration metadata**: `access_token_expires_in` / `refresh_token_expires_in` (seconds) plus `_expires_at` (absolute timestamps) — computed from the actual decoded token claims, not assumed from config, so the response is always accurate even if config changes between token creation and response serialization.

## ⚠️ Known limitation — by design, not a bug

**This endpoint can only authenticate users whose password was hashed by the NEW Registration API (Step 3, Argon2).** Users who registered through the existing `/auth/register` (bcrypt) will get `InvalidCredentialsException` here — same response as a wrong password, deliberately: `_verify()` catches `passlib.exc.UnknownHashError` (raised when Argon2-only `PasswordService` is asked to verify a bcrypt hash) and treats it identically to a failed password check. **Never reveal which hashing scheme an account uses** — that's an account-enumeration/fingerprinting side channel, so failing closed and silently is the correct security behavior here, not something to "fix" by adding bcrypt support back into `PasswordService` without a deliberate decision (see Step 1's README).

## Database
No schema change. Uses existing `users`, `refresh_tokens`, `login_history` tables.

## Explicitly out of scope for this step
- **Refresh endpoint** — not implemented, per instruction. A token issued here cannot yet be renewed through this isolated track; the existing `/auth/refresh` only works with tokens issued by the existing system (different claim shape — see `auth/jwt/README.md`'s claims comparison table).
- **Replacing the existing auth system** — not done, not attempted.

## Tests
`tests/test_login_service.py` — 6 tests, including a dedicated case for the bcrypt-hash-graceful-rejection behavior (`test_login_rejects_bcrypt_hash_gracefully`) and one asserting the exact expiration metadata values match the configured 15 min / 30 day durations.

## Future improvements
- Once a cutover decision is made (see registration module's README), this and the registration module's duplicated `_issue_tokens()`-style logic should be extracted into one shared helper — acceptable duplication for now since each step was built in isolation per its own explicit scope.
- A Step 5 "Refresh Token" endpoint (explicitly deferred here) would complete this isolated track end-to-end.
