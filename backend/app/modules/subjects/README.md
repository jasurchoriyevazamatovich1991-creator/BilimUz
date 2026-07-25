# Subjects Module — BilimUz

## Architecture
`router.py` → `dependencies.py` (RBAC, DI) → `service.py` (rules) → `repository.py` (queries) → `subjects` table. Same 8-layer pattern as `auth`; nothing new architecturally, this module proves the pattern generalizes.

## Business rules
- Subject names are unique (case-insensitive) — enforced in `service.py`, not just the DB constraint, so the API returns a clean `409` instead of a raw integrity-error.
- Delete is **soft**: `deleted_at` is set, `status` becomes `archived`. Hard-deleting a subject would orphan every `topic`/`test` that references it — never done.
- Sort field is allowlisted (`constants.ALLOWED_SORT_FIELDS`) before it ever reaches SQLAlchemy's `getattr` — closes the door on sort-parameter injection (`?sort=__class__` etc.). Covered by `test_invalid_sort_field_falls_back_to_default`.

## Database
Table: `subjects` (see `database/schema/schema_v2.sql`, Module 7). Model in `models.py` composes `UUIDPrimaryKeyMixin + TimestampMixin + AuditMixin + StatusMixin`.

## API

```
GET    /api/v1/subjects?page=&per_page=&search=&status=&sort=   Public
GET    /api/v1/subjects/{id}                                     Public
POST   /api/v1/subjects                                          Admin, Super Admin
PATCH  /api/v1/subjects/{id}                                      Admin, Super Admin
DELETE /api/v1/subjects/{id}                                      Admin, Super Admin
```

Response envelope (platform-wide standard, see `core/schemas.py`):
```json
{ "success": true, "message": "Fanlar ro'yxati.", "data": { "items": [...], "meta": {...} }, "errors": null }
```

## Flow — create subject

```
Client → router.create_subject → require_roles('Admin','Super Admin')
       → service.create_subject → repo.get_by_name (uniqueness check)
       → repo.create → repo.commit → SubjectOut → success_response
```

## Security
- Write endpoints protected by `auth.dependencies.require_roles` — reused, not reimplemented (DRY).
- `name`/`color` validated in `validators.py` before ever reaching the DB.
- Read endpoints public by design (browsing subjects is part of the public marketing site per `docs/UI-UX`).

## Future improvements
- Redis cache for `GET /subjects` (list rarely changes, read constantly — v2.0 roadmap item, "Cache where necessary").
- Bulk import endpoint for admins seeding many subjects at once (batch insert, avoids N sequential `POST` calls).
