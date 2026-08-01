# Auth Module — BilimUz

## Architecture

Layered: `router.py` (HTTP) → `dependencies.py` / `validators.py` (cross-cutting) → `service.py` (business rules) → `repository.py` (persistence) → PostgreSQL. Password hashing and JWT logic live in `core/security/` (shared infrastructure, since other modules — e.g. `permissions`'s `require_permission()` — also need JWT verification).

`service.py` never imports anything from `fastapi` — it raises `AppException` subclasses from `core/exceptions.py`, which `main.py` maps to HTTP responses globally. This means `AuthService` can be called from a future Telegram bot or CLI seed script with zero changes.

**Sprint 4 note (Auth Cutover)**: this module previously had a parallel, isolated Sprint 3 implementation (`auth/security/`, `auth/jwt/`, `auth/registration/`, `auth/login/`, `auth/refresh/`, `auth/me/`, mounted at `-v2` paths). That implementation has been merged into this single module and those folders removed — there is now exactly one auth system. See `docs/ADR/ADR-009-Auth-Cutover.md` for the full decision record.

## Business logic

| Flow | Steps |
|---|---|
| **Register** | Check phone/email uniqueness → validate password strength (`PasswordService`, structured errors) → hash password (**Argon2**) → create `User` (status=`pending_verification`) → generate 6-digit code → hash and store it → return `(user, plain_code)` so the caller (router, later a notifications service) can deliver it. |
| **Verify** | Look up the latest unused code for the user → reject if 5+ failed attempts → compare hash (constant-time) → mark code used, activate user. |
| **Login** | Look up user by phone/email → verify password hash (Argon2) → issue access (15 min) + refresh (30 day) token pair (JWT, with `nbf` claim) → record `login_history`. |
| **Refresh** | Decode refresh JWT → look up its hashed value in `refresh_tokens` (must not be revoked) → **revoke it** (rotation — a refresh token is single-use) → issue a new pair. |
| **Logout** | Decode refresh JWT (best-effort) → revoke it. Idempotent — logging out twice is not an error. |

## Database

Tables owned by this module: `refresh_tokens`, `login_history`, `verification_codes`, `password_history` (see `models.py`). `users` and `roles` are owned by their own modules — auth only reads/writes `User` rows, it doesn't own the table.

All tables inherit `UUIDPrimaryKeyMixin` + `TimestampMixin` (`created_at`, `updated_at`, `deleted_at`) from `core/mixins.py`, per the project's database rules.

## API

See `docs/API/api_blueprint.md` for the full contract. Summary:

```
POST /api/v1/auth/register        → 201, {user_id, debug_code}
POST /api/v1/auth/verify          → 200, UserPublic
POST /api/v1/auth/login           → 200, {access_token, refresh_token}
POST /api/v1/auth/refresh         → 200, {access_token, refresh_token}
POST /api/v1/auth/logout          → 204
POST /api/v1/auth/logout-all      → 200, {devices_revoked}
GET  /api/v1/auth/sessions        → 200, [SessionOut]
POST /api/v1/auth/change-password → 200
GET  /api/v1/auth/me              → 200, UserPublic  (requires Bearer token)
```

**These are the only auth endpoints in the platform** — the Sprint 3 `-v2` paths (`/auth/registration`, `/auth/login-v2`, `/auth/refresh-v2`, `/auth/me-v2`) no longer exist.

## Security notes

- **Passwords: Argon2** (`core/security/password_service.py`) — replaces the original bcrypt implementation as of Sprint 4.
- **JWT: `core/security/jwt_service.py`** — typed `TokenPayload`, includes `nbf` claim (not-before), which the original implementation lacked.
- **Password policy: 12+ characters**, upper+lower+digit+special, common-password denylist — the single, final value (Sprint 3 briefly explored 10 chars in isolation; 12 was kept, per `docs/ADR/ADR-009-Auth-Cutover.md`).
- Refresh tokens: stored **hashed** (SHA-256) in `refresh_tokens.token_hash` — a DB leak alone does not grant access. Rotation on every refresh (old token revoked immediately).
- Verification codes: stored hashed, max 5 attempts, compared with `secrets.compare_digest` (timing-safe).
- `GET /me` and all protected routes go through `get_current_user` in `dependencies.py`, shared by every other module. It now catches both `jwt.PyJWTError` and `pydantic.ValidationError` when decoding — a real gap found during Sprint 3's isolated build (an incompatible token payload previously risked an unhandled 500), fixed permanently here.
- No internal error (stack trace, SQL message) ever reaches the client — `app_exception_handler` in `core/exceptions.py` is the only place that builds the error response.

## Known placeholder (flagged, not hidden)

`router.py`'s `register` endpoint currently returns `debug_code` in the response body instead of sending it via SMS — marked with `# TODO(notifications module)`. This is intentional: the `notifications` module (SMS/email provider integration) doesn't exist yet.

## Security hardening (Chief Security Engineer revision, Sprint 1; algorithm updated Sprint 4)

| Control | Implementation |
|---|---|
| Password policy | 12+ chars, upper+lower+digit+special, weak-password denylist (`core/security/password_service.py`) |
| Password hashing | **Argon2** (`core/security/password_service.py`) |
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
- Breached-password check against a real corpus (e.g. Have I Been Pwned range API) instead of the small local denylist.
