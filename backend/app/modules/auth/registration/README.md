# Registration Module — `app/modules/auth/registration/`

Sprint 3, Step 3: Register API — the first place `PasswordService` (Step 1) and `JWTService` (Step 2) are actually wired into a runnable endpoint.

## Endpoint

```
POST /api/v1/auth/registration
```

**Deliberately NOT `/api/v1/auth/register`** — the existing endpoint at that path (in `app/modules/auth/router.py`) is untouched, per this step's explicit scope ("Do NOT modify login endpoint", and by extension the file containing it). This new endpoint is mounted at a different path so both can exist, be tested, and be compared side by side without collision.

## What it does

1. Rejects duplicate **phone** or **email** (reusing the existing, unmodified `AuthRepository.get_user_by_identifier` — no repository changes were needed).
2. Validates password strength via `PasswordService.validate_password_strength()` — **all** violated rules surface at once (`WeakPasswordException.errors`), not just the first.
3. Hashes the password with **Argon2** (`PasswordService.hash_password()`).
4. Creates the `User` row (default role: Student, same constant reused read-only from `auth/service.py`).
5. Issues an access + refresh token pair via **JWTService**, persists the refresh token (hashed, via the existing `AuthRepository.create_refresh_token` — same rotation-ready pattern as the rest of the codebase).
6. Returns the created user **without the password hash** (`RegisteredUserOut` has no such field) plus the token pair.

## ⚠️ Policy differences from the existing `/auth/register` — flagged, not hidden

| | Existing `/auth/register` | This endpoint |
|---|---|---|
| Password hash | bcrypt | Argon2 |
| Password policy | 12+ chars (Pydantic validator, first-error-only) | 10+ chars (service-layer, all errors at once) |
| Account status after registration | `pending_verification` — must verify phone before use | `pending_verification` **but tokens are issued immediately** |
| Response | `{user_id, debug_code}` | Full user object + token pair |

**The "tokens issued before verification" difference is a deliberate design choice for this isolated endpoint, not an oversight** — it demonstrates JWTService integration end-to-end. Whether BilimUz's actual policy should allow token issuance before phone verification is a product decision that needs to be made explicitly before this endpoint replaces the old one — not decided implicitly by which code happened to ship first.

## Database
No schema change. Uses the existing `users` and `refresh_tokens` tables exactly as `auth/service.py` does.

## Tests
`tests/test_registration_service.py` — uses **real** `PasswordService` and `JWTService` instances (both stateless, no mocking needed), only the repository is mocked. This proves the two Step 1/2 services genuinely integrate, not just that each works in isolation.

## Future improvements
- Decide the cutover plan: replace `/auth/register` with this implementation (retiring bcrypt + the old validator), keep both indefinitely, or retire this one — see the parallel "Known conflict" notes in `auth/security/README.md` and `auth/jwt/README.md`, which all need to be resolved together.
- If token-before-verification is not the desired policy, remove `_issue_tokens()` from `register()` and return only the user + a verification-code flow (matching the existing endpoint's behavior).
- Add rate limiting (`core/middleware/rate_limit.py`, already used by the existing `/auth/register`) once this endpoint's cutover status is decided — not added preemptively to keep this step's diff focused on the three things asked for (schemas, service, router).
