# Auth Module — BilimUz

## Architecture

Layered: `router.py` (HTTP) → `dependencies.py` / `validators.py` (cross-cutting) → `service.py` (business rules) → `repository.py` (persistence) → PostgreSQL.

`service.py` never imports anything from `fastapi` — it raises `AppException` subclasses from `core/exceptions.py`, which `main.py` maps to HTTP responses globally. This means `AuthService` can be called from a future Telegram bot or CLI seed script with zero changes.

## Business logic

| Flow | Steps |
|---|---|
| **Register** | Check phone/email uniqueness → hash password (bcrypt) → create `User` (status=`pending_verification`) → generate 6-digit code → hash and store it → return `(user, plain_code)` so the caller (router, later a notifications service) can deliver it. |
| **Verify** | Look up the latest unused code for the user → reject if 5+ failed attempts → compare hash (constant-time) → mark code used, activate user. |
| **Login** | Look up user by phone/email → verify password hash → issue access (15 min) + refresh (30 day) token pair → record `login_history`. |
| **Refresh** | Decode refresh JWT → look up its hashed value in `refresh_tokens` (must not be revoked) → **revoke it** (rotation — a refresh token is single-use) → issue a new pair. |
| **Logout** | Decode refresh JWT (best-effort) → revoke it. Idempotent — logging out twice is not an error. |

## Database

Tables owned by this module: `refresh_tokens`, `login_history`, `verification_codes` (see `models.py`). `users` and `roles` are owned by their own modules (`app/users/`, `app/roles/`) — auth only reads/writes `User` rows, it doesn't own the table.

All tables inherit `UUIDPrimaryKeyMixin` + `TimestampMixin` (`created_at`, `updated_at`, `deleted_at`) from `core/mixins.py`, per the project's database rules.

## API

See `docs/API/api_blueprint.md` for the full contract. Summary:

```
POST /api/v1/auth/register   → 201, {user_id, debug_code}
POST /api/v1/auth/verify     → 200, UserPublic
POST /api/v1/auth/login      → 200, {access_token, refresh_token}
POST /api/v1/auth/refresh    → 200, {access_token, refresh_token}
POST /api/v1/auth/logout     → 204
GET  /api/v1/auth/me         → 200, UserPublic  (requires Bearer token)
```

## Flow diagram

```
Client                Router              Service             Repository        DB
  │  POST /register     │                    │                    │             │
  ├────────────────────▶│                    │                    │             │
  │                      │ register(data)     │                    │             │
  │                      ├───────────────────▶│                    │             │
  │                      │                    │ get_user_by_identifier            │
  │                      │                    ├───────────────────▶│────────────▶│
  │                      │                    │◀──────────────────┤◀────────────┤
  │                      │                    │ hash_password()    │             │
  │                      │                    │ create_user()       │             │
  │                      │                    ├───────────────────▶│────────────▶│
  │                      │◀───────────────────┤ (user, plain_code)  │             │
  │◀─────────────────────┤ 201 {user_id, code}│                    │             │
```

## Security notes

- Passwords: bcrypt, 12 rounds (`core/security.py`).
- Refresh tokens: stored **hashed** (SHA-256) in `refresh_tokens.token_hash` — a DB leak alone does not grant access. Rotation on every refresh (old token revoked immediately).
- Verification codes: stored hashed, max 5 attempts, compared with `secrets.compare_digest` (timing-safe).
- `GET /me` and all protected routes go through `get_current_user` in `dependencies.py`, shared by every other module.
- No internal error (stack trace, SQL message) ever reaches the client — `app_exception_handler` in `core/exceptions.py` is the only place that builds the error response.

## Known placeholder (flagged, not hidden)

`router.py`'s `register` endpoint currently returns `debug_code` in the response body instead of sending it via SMS — marked with `# TODO(notifications module)`. This is intentional: the `notifications` module (SMS/email provider integration) doesn't exist yet. Once it does, this line is deleted and replaced with a call to it. This is the **only** simplification in this module — everything else (hashing, token rotation, RBAC dependency, validators) is production logic.

## Security hardening (Chief Security Engineer revision)

| Control | Implementation |
|---|---|
| Password policy | 12+ chars, upper+lower+digit+special, weak-password denylist (`validators.py`) |
| Password reuse prevention | Last 5 hashes stored in `password_history`, checked on change (`service.change_password`) |
| Rate limiting | Redis fixed-window, per-IP, on `/register` `/login` `/verify` (`core/middleware/rate_limit.py`) |
| Device management | `GET /sessions`, `POST /logout-all` — list/revoke active refresh tokens |
| Forced re-login on password change | `change_password` revokes every refresh token for that user |
| Audit trail | `auth.login_success`, `auth.login_failed`, `auth.password_changed`, `auth.logout_all` etc. written to `audit_logs` via `core/audit.py` |
| Security headers | CSP, X-Frame-Options, HSTS, etc. on every response (`core/middleware/security_headers.py`) |
| CORS | Explicit origin allowlist, restricted methods/headers — never `*` (`main.py`) |
| Never logged | Passwords, plaintext verification codes, and raw JWTs never appear in `log_action()` calls — only IDs and counts |

**Known deviation (flagged, not hidden)**: full OWASP-grade rate limiting would also key on the request body's `identifier` (phone/email), not just IP, to stop distributed attacks against one account. The current `rate_limit()` dependency is IP-only.

## Future improvements

- 2FA (TOTP) — `users.two_factor_enabled` column already reserved in the DB blueprint.
- Google / Telegram OAuth login (columns reserved on `users`).
- Move from sync SQLAlchemy `Session` to `AsyncSession` if request volume requires it — `repository.py` is the only file that would need to change, by design.
- Breached-password check against a real corpus (e.g. Have I Been Pwned range API) instead of the small local denylist in `constants.py`.

