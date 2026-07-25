# Permissions Module — BilimUz

## Architecture
Same layered pattern, with one structural difference: this module owns **two** tables (`permissions`, `role_permissions`) because they're a single cohesive concern — matching how `database/schema/schema_v2.sql` groups them as one "Module 4". `repository.py` and `service.py` each contain two classes (`PermissionRepository`/`RolePermissionRepository`, `PermissionService`/`RolePermissionService`) rather than being split into two modules, since a permission grant is meaningless without the permission existing, and vice versa.

This module also introduces **`require_permission()`** in `dependencies.py` — the permission-based sibling of `auth.dependencies.require_roles()`. It lives here, not in `auth`, because it depends on `RolePermissionService`; `auth` must stay independent of every other module (ADR-005).

## Business rules — this is the capstone of ADR-006
`docs/ADR/ADR-006-Use-RBAC.md` documented in Sprint 1 that BilimUz would start with pure role checks and evolve to permission checks **without a schema migration**, because `roles`/`permissions`/`role_permissions` already existed. This module delivers that:

- **Permission codes are immutable and SCREAMING_SNAKE_CASE** (`CREATE_TEST`, `VIEW_ANALYTICS`) — enforced by `validators.py`, exactly mirroring why role names are immutable in the `roles` module: every `require_permission("CODE")` call elsewhere in the codebase depends on the code staying stable.
- **`role_has_permission_code()` is a single indexed join** (`role_permissions` ⋈ `permissions`, filtered on both being `status='active'` and not soft-deleted) — kept as one query, not N+1, so the RBAC check stays fast under load. This is the query every protected request runs.
- **Creating/modifying permissions and grants is Super-Admin-only** — misconfiguring either changes what every user with a role can do, platform-wide, which is a higher blast radius than a single user or even a single role edit.
- **Migration path is additive, not a rewrite**: a router changes one line — `Depends(require_roles("Admin", "Super Admin"))` becomes `Depends(require_permission("SUBJECTS_MANAGE"))` — and both dependencies can coexist indefinitely. No module is forced to migrate before it's ready.

## Database
Tables: `permissions`, `role_permissions` (Module 4, `database/schema/schema_v2.sql`). No schema change — models were written to match the existing tables exactly (including the `role_permissions`-as-full-entity trade-off already documented there).

## API

```
GET    /api/v1/permissions                         — list/search/filter    Admin, Super Admin
GET    /api/v1/permissions/{id}                      — get one                Admin, Super Admin
POST   /api/v1/permissions                            — create                  Super Admin only
PATCH  /api/v1/permissions/{id}                         — update                  Super Admin only
DELETE /api/v1/permissions/{id}                          — soft delete             Super Admin only
GET    /api/v1/permissions/roles/{role_id}                — list role's grants      Admin, Super Admin
POST   /api/v1/permissions/roles/{role_id}/assign           — grant to role           Super Admin only
DELETE /api/v1/permissions/roles/{role_id}/revoke/{perm_id}  — revoke from role         Super Admin only
```

## Flow — a protected endpoint using require_permission

```
Client → Router: Depends(require_permission('SUBJECTS_MANAGE'))
  → dependencies.get_current_user()          [existing auth check — is this a valid token?]
  → dependencies.get_role_permission_service()
  → service.role_has_permission(user.role_id, 'SUBJECTS_MANAGE')
      → repo.role_has_permission_code()  [one indexed JOIN query]
  → False → PermissionDeniedException (403)
  → True  → request proceeds, handler runs
```

## Security
- Every write endpoint is Super-Admin-only, reusing `auth.dependencies.require_roles` (not reimplemented).
- Every permission/grant change is audit-logged (`permission.created`, `role_permission.granted`, `role_permission.revoked`, etc.) via `core/audit.py`.
- `require_permission()` fails closed: any exception path or missing grant results in `PermissionDeniedException`, never silent allow.

## Future improvements
- Seed a baseline permission catalog matching the 25-module system (`database/seeds/` — not yet written) so `permissions` isn't an empty table on a fresh install.
- Cache `role_has_permission_code()` results in Redis (role→permission grants change rarely, checked on nearly every request) — first real candidate for the "Cache where necessary" principle, now that the query pattern is proven.
- Migrate `subjects`' and `users`' `require_roles(...)` calls to `require_permission(...)` one endpoint at a time, per the ADR-006 migration path — no endpoint is forced to move until its permission is actually seeded.
