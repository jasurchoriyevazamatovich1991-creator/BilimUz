# Refresh Token Module — `app/modules/auth/refresh/`

Sprint 3, Step 5: Refresh Token API using `JWTService` exclusively for token operations.

## Endpoint

```
POST /api/v1/auth/refresh-v2
```

**Deliberately NOT `/api/v1/auth/refresh`** — same isolation pattern as registration/login. The existing refresh endpoint in `app/modules/auth/router.py` is untouched.

## What it does

1. Decodes the presented refresh token via `JWTService.decode_token()`.
2. Verifies it's a `refresh`-type token, not an `access` token (`verify_token_type()`).
3. Looks up the stored, hashed token by `jti` (existing `AuthRepository.get_refresh_token_by_jti` — no repository changes needed) and confirms the hash matches.
4. **Always rotates**: revokes the old token (`AuthRepository.revoke_refresh_token`) and issues a brand-new access + refresh pair before returning.
5. Returns full token metadata (access + refresh tokens, type, expiry — same shape as the Login API's response for consistency).

## Rotation: "optional" in the spec, always-on in the implementation

The requirement said "optionally rotate refresh token." This was interpreted as *the endpoint may perform rotation* (as opposed to *must never* rotate) — and once that door is open, always-rotating is the only defensible default: a stolen-but-still-valid refresh token that gets reused by an attacker after the legitimate owner has already refreshed would otherwise still work. No toggle is exposed to the API caller; this isn't a decision a client should get to make.

## ⚠️ A real compatibility gap was found and handled while building this

Tokens issued by the **old** system (`core/security.py`) don't carry an `nbf` claim (added new in Step 2). `JWTService.decode_token()` builds a `TokenPayload` that **requires** `nbf` — feeding it an old-style token doesn't raise a JWT error, it raises `pydantic.ValidationError`, which was **not** being caught anywhere. Left unhandled, this would have surfaced as an unhandled 500 (raw internal error, `.cursor/prompts/05-security.md`: "Never expose stack traces") instead of the clean 401 this endpoint is supposed to return for any invalid token.

**Fixed in `_decode_or_reject()`**: catches both `jwt.PyJWTError` (expired/tampered/malformed) and `pydantic.ValidationError` (structurally incompatible, e.g. old-system tokens) and converts either into `InvalidTokenException`. Covered by a dedicated test, `test_refresh_rejects_old_system_token_missing_nbf_claim`.

## Database
No schema change. Uses the existing `refresh_tokens` table — the same table, same repository methods the old system and Steps 3-4 already use. This is data-layer reuse, not "integrating with the old JWT system" (which refers to `core/security.py`'s token functions, never imported here).

## Explicitly out of scope for this step
- **Logout** — not implemented, per instruction.
- **Integration with the old JWT system** — not done; `core.security.create_access_token/create_refresh_token/decode_token` are never called from this module.

## Tests
6 tests: malformed token, access-token-used-as-refresh, unknown `jti`, hash mismatch, the old-system-compatibility case, and a full successful-rotation path asserting the old token is revoked, a new one is persisted, and the returned refresh token is genuinely different from the input.

## Future improvements
- This is the fourth and final piece of the isolated Sprint 3 track (Password → JWT → Register → Login → Refresh). The next real decision is the **cutover plan** referenced in every prior step's README: replace the old bcrypt/12-char/no-`nbf` system with this one, run both indefinitely, or retire this track — not a decision to make implicitly by which code happens to exist.
