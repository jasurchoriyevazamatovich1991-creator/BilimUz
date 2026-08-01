# Grades Module — BilimUz

## Architecture

Same 8-layer pattern as `auth`/`users`/`subjects`/`roles`/`permissions`: `router.py` (HTTP) → `dependencies.py` (DI) → `service.py` (business rules) → `repository.py` (persistence) → PostgreSQL. Import style, exception handling, and response envelope are identical to `auth`/`users` — no deviations.

## Business rules

- **A grade represents a curriculum level** — school grades (`5-sinf`...`11-sinf`), or a special category (`Attestatsiya`, `Milliy sertifikat`, `Abituriyent`). It's a lightweight lookup entity that `Topics` and (later) `Tests` optionally scope to.
- **Name is unique** (case-insensitive) and **immutable after creation** — same rule as `roles`/`subjects`: renaming in place could silently break anything that filtered by the old name. `GradeUpdateRequest` has no `name` field at all.
- **Soft delete only** — `deleted_at` + `status='archived'`. A grade that's already referenced by `topics.grade_id` (nullable FK) is never hard-deleted, so existing topic associations aren't orphaned.

## Database

Table: `grades` (Module 8, `database/schema/schema_v2.sql`). Model composes `UUIDPrimaryKeyMixin + TimestampMixin + AuditMixin + StatusMixin` — identical mixin set to every other module.

## API

```
GET    /api/v1/grades              — list/search/filter/paginate      Public
GET    /api/v1/grades/{id}          — get one grade                     Public
POST   /api/v1/grades                — create                              Admin, Super Admin
PATCH  /api/v1/grades/{id}            — update status                        Admin, Super Admin
DELETE /api/v1/grades/{id}             — soft delete                          Admin, Super Admin
```

Read endpoints are public — the grade list needs to populate filter dropdowns (e.g. a public test-catalog page) before a user logs in, same reasoning as `subjects`.

Full Swagger descriptions (summary + description per parameter) are in `router.py` — visible at `/docs`.

## Flow — create grade

```
Router (require_roles('Admin','Super Admin'))
  → service.create_grade(data, actor_id)
      → repo.get_by_name(data.name)  [case-insensitive uniqueness check]
      → repo.create(Grade(...))
      → core.audit.log_action('grade.created')
      → repo.commit()
```

## Security

Write endpoints reuse `auth.dependencies.require_roles` (not reimplemented). Every create/update/delete is audit-logged via `core/audit.py`.

## Tests

`tests/test_grade_service.py` — 7 tests: duplicate-name rejection, successful creation, not-found, status update, soft delete, and two schema-level validation edge cases (invalid status value, invalid name length boundaries).

## Future improvements

- `GET /grades/{id}/topics` — list topics scoped to a grade (once `topics` module, built next in this same sprint, is live).
- Once the `permissions` module has seeded permission codes for this module, `require_roles("Admin", "Super Admin")` should migrate to `require_permission("grades.manage")` per `docs/ADR/ADR-006-Use-RBAC.md`.
