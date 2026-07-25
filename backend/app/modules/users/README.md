# Users Module — BilimUz

## Architecture
Same 8-layer pattern as `auth`/`subjects`. This module owns *user management* (profile edits, admin listing, role assignment) — it deliberately does NOT own registration, login, or password handling; those stay in `auth`, which owns identity/credentials. Keeping the boundary here prevents `users` and `auth` from importing each other's business logic.

## Business rules
- **Self-service vs admin-service are different schemas**: `UserSelfUpdateRequest` has no `status`/`role_id` fields at all — a user literally cannot send a request that would escalate their own privileges, because Pydantic drops unknown fields rather than erroring loudly. This is intentional defense in depth (see `docs/API/api_blueprint.md` for the general pattern).
- **Role changes are Super-Admin-only** (`PATCH /users/{id}/role`, `require_roles("Super Admin")`) — an ordinary Admin cannot grant Super Admin to anyone, including themselves. This is the single highest-privilege action in the platform and gets its own endpoint rather than being bundled into the general update endpoint.
- **No one can modify their own account through the admin endpoints** (`CannotModifySelfException`) — even a Super Admin must use `/users/me` for self-edits. This guarantees every privileged change has two actors (the admin and the target), which matters for audit trails and for containing a compromised admin token.
- `status='banned'` is intentionally excluded from `ADMIN_SETTABLE_STATUSES` — banning is significant enough to warrant its own future endpoint with a mandatory reason, not a silent field in a generic PATCH.

## Database
Table: `users` (Module 2 in `database/schema/schema_v2.sql`). No new tables — this module only adds behavior around the existing `User` model (`app/users/models.py`, already built in Sprint 1).

## API

```
GET    /api/v1/users/me            — my own profile                    Any authenticated user
PATCH  /api/v1/users/me             — update my own profile              Any authenticated user
GET    /api/v1/users                 — list/search/filter/paginate         Admin, Super Admin
GET    /api/v1/users/{id}             — get one user                        Admin, Super Admin
PATCH  /api/v1/users/{id}              — admin edit (name, status)            Admin, Super Admin
PATCH  /api/v1/users/{id}/role          — reassign role                        Super Admin only
```

## Flow — admin changes another user's role

```
Router (require_roles('Super Admin'))
  → service.change_role(target_id, new_role_id, actor_id)
      → refuse if target_id == actor_id (CannotModifySelfException)
      → repo.get_by_id(target_id)
      → repo.update({role_id: new_role_id})
      → core.audit.log_action('user.role_changed', old + new role in metadata)
      → repo.commit()
```

## Security
- Every write endpoint goes through `auth.dependencies.require_roles` (reused, not reimplemented).
- Role changes and admin edits are audit-logged with before/after values where relevant (`user.role_changed` metadata includes both `old_role_id` and `new_role_id`).
- List/search endpoints are Admin-only — user PII (phone, email) is never exposed to unauthenticated or unprivileged callers via this module.

## Future improvements
- `ban_user(user_id, reason)` — dedicated endpoint once `status='banned'` needs a mandatory audit trail with reason text.
- Once the `permissions` module (Sprint 2, stage 3) exists, `require_roles("Admin", "Super Admin")` on list/get endpoints should migrate to `require_permission("users.view")` per `docs/ADR/ADR-006-Use-RBAC.md`.
