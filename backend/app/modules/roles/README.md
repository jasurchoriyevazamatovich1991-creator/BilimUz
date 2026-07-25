# Roles Module — BilimUz

## Architecture
Same 8-layer pattern as `auth`/`users`/`subjects`. One documented exception: `repository.py` imports `app.modules.users.models.User` (read-only, to count how many users hold a role before allowing deletion). This is a deliberate, one-directional dependency (`roles → users`, never the reverse) — not a violation of module isolation, since it doesn't import `users`' service or repository, only its ORM model for a single COUNT query.

## Business rules
- **The 8 seeded system roles (`Super Admin`, `Admin`, `Moderator`, `Teacher`, `Applicant`, `Student`, `Parent`, `Guest`) can never be deleted, and can never be deactivated** — every `require_roles("Admin")`-style check across the entire codebase depends on these names existing and being active. `SYSTEM_ROLE_NAMES` in `constants.py` is the single source of truth for this list.
- **Role name is immutable after creation** (`RoleUpdateRequest` has no `name` field at all) — renaming a role in place would silently break every `require_roles("Old Name")` call elsewhere in the codebase with no error at the call site. Changing what a role is called is a create-new + migrate-users operation, not an edit.
- **A custom (non-system) role cannot be deleted while users are still assigned to it** (`RoleInUseException`) — prevents orphaned `role_id` foreign keys, enforced in the service layer before the DB constraint would even be reached.
- Every create/update/delete is audit-logged (`role.created`, `role.updated`, `role.deleted`) via `core/audit.py`.

## Database
Table: `roles` (Module 3, `database/schema/schema_v2.sql`). No schema change — this module adds behavior around the existing `Role` model built in Sprint 1.

## API

```
GET    /api/v1/roles              — list/search/filter/paginate      Admin, Super Admin
GET    /api/v1/roles/{id}          — get one role                      Admin, Super Admin
POST   /api/v1/roles                — create a new (custom) role          Super Admin only
PATCH  /api/v1/roles/{id}            — update description/status            Super Admin only
DELETE /api/v1/roles/{id}             — soft delete (blocked for system/in-use roles)  Super Admin only
```

All endpoints require at least Admin — the role list reveals the platform's privilege structure and is never public. Write operations require Super Admin specifically, since a role change can eventually affect every user later assigned to it.

## Flow — deleting a role

```
Router (require_roles('Super Admin'))
  → service.delete_role(role_id, actor_id)
      → get_role(role_id)  [raises RoleNotFoundException if missing]
      → if role.name in SYSTEM_ROLE_NAMES → SystemRoleProtectedException
      → repo.count_users_with_role(role_id)
      → if count > 0 → RoleInUseException
      → repo.soft_delete()  [sets deleted_at + status='archived']
      → core.audit.log_action('role.deleted')
      → repo.commit()
```

## Security
- Read endpoints: Admin+. Write endpoints: Super Admin only, reusing `auth.dependencies.require_roles` (no reimplementation).
- System role protection is enforced in **two places independently** — delete AND status-deactivation — closing both paths that could disable a core privilege level.

## Future improvements
- Once the `permissions` module exists (next in Sprint 2), `RoleOut` should include the role's attached permissions list, and `require_roles("Admin", "Super Admin")` on these endpoints should migrate to `require_permission("roles.manage")` per `docs/ADR/ADR-006-Use-RBAC.md`.
- A `GET /roles/{id}/users` endpoint (paginated list of users holding a role) would make the `RoleInUseException` actionable from the UI (show *which* users need reassignment, not just a count).
