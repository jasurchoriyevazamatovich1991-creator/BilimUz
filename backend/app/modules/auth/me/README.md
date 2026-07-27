# Profile Module — `app/modules/auth/me/`

Sprint 3, Step 6: GET /me using `JWTService` exclusively for access-token verification.

## Endpoint

```
GET /api/v1/auth/me-v2
Authorization: Bearer <access_token>
```

**Deliberately NOT `/api/v1/auth/me`** — same isolation pattern as every other Sprint 3 step. The existing `/auth/me` in `auth/router.py` (and its `get_current_user()` dependency in `auth/dependencies.py`) are completely untouched.

## What it does

1. `get_current_user_v2()` (in `dependencies.py`) extracts the Bearer token, decodes it via `JWTService.decode_token()`, and verifies it's an `access`-type token (`verify_token_type()`) — rejecting a refresh token used here, same defense as the existing system's `get_current_user()`.
2. Looks up the user by the token's `sub` claim via the existing, unmodified `AuthRepository.get_user_by_id()` — no repository changes needed.
3. `MeService.get_profile()` shapes the response: **never includes `password_hash`**, includes role info (`RoleInfo`: id + name) when the relationship resolves, `None` otherwise (per "if available").

## Same compatibility handling as Step 5

`get_current_user_v2()` catches both `jwt.PyJWTError` and `pydantic.ValidationError` when decoding — the latter specifically covers old-system tokens (no `nbf` claim), which would otherwise raise an unhandled 500 instead of a clean 401. Identical fix to `refresh/service.py`'s `_decode_or_reject()`, applied here because this is the second place in the isolated track that decodes a caller-supplied token.

## "Role information if available" — what "unavailable" means here

`User.role` is a SQLAlchemy relationship; it resolves via lazy-load in a real request (the session is still open). It would be `None`-equivalent only in a genuinely broken data state (a `role_id` pointing nowhere — prevented by the FK constraint in `schema_v2.sql`) or in tests using a plain object without a `role` attribute set — covered by `test_get_profile_role_is_none_when_unavailable`.

## Database
No schema change. Read-only use of `users` and `roles` (via the existing relationship) — no new queries beyond what `AuthRepository.get_user_by_id` already does.

## Explicitly out of scope for this step
- **Logout** — not implemented, per instruction.
- **Integration with the old auth system** — `auth/dependencies.py`'s `get_current_user()` is never imported or called here; this module has its own independent `get_current_user_v2()`.

## Tests
4 tests on `MeService` (password-hash absence, role-present, role-absent, core field mapping) — deliberately no DB/mocking needed since the service is pure shaping logic operating on any object with the right attributes.

## Future improvements
- This completes the full isolated Sprint 3 track: Password → JWT → Register → Login → Refresh → Me. Every module's README points to the same open question — the **cutover decision**. That should be the next explicit step before any further isolated endpoints are added, to avoid an ever-growing parallel `-v2` surface with no plan to converge.
