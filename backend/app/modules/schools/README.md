# Schools Module — BilimUz

Full design rationale: `docs/Sprint10_Schools_LearningCenters_Architecture.md` (approved).

## Architecture

Same 8-layer pattern. Structurally closest to `grades` (Sprint 5) — a simple, standalone lookup entity with zero dependency on any other module. **No provider abstraction, no vendor boundary** — plain CRUD.

## ⚠️ Known scope boundary: no consumer yet

`profiles.school_id` (schema Module 2) references this table, but `profiles` itself has **never been implemented** as an ORM model anywhere in the codebase (verified: `app/modules/users/models.py` defines only `User`). This means a user cannot yet be assigned to a school through the running system — `schools` ships as a complete, valid, standalone catalog this sprint, with the assignment feature explicitly deferred to a future `Profile` sprint (approved decision, not an oversight).

## Business rules

- **`name` is NOT required to be unique** — a deliberate difference from `grades`/`subjects`. The schema has no `UNIQUE` constraint on `schools.name`, which matches reality: two different towns can each have a "1-maktab". Tested explicitly (`test_create_succeeds_without_uniqueness_check`).
- **Phone validation is intentionally broader than the strict mobile-only pattern used elsewhere**: accepts any `+998` + 9-digit E.164-style number, not restricted to mobile-operator prefixes (approved decision 2) — covers institutional landlines.
- **The phone validator is defined locally in this module** (`validators.py`), not imported from `app.modules.auth.validators`, even though the resulting regex is equivalent — this keeps `schools`' cross-module dependency count at zero, per the approved architecture.
- **Soft delete only** — `deleted_at` + `status='archived'`, same convention as every other lookup module.

## Database

Table: `schools` (Module 5, `database/schema/schema_v2.sql`). No schema change, no migration — the table already existed in the baseline (`0001_initial_schema.py`).

## API

```
GET    /api/v1/schools              — list/search/filter/paginate      Public
GET    /api/v1/schools/{id}          — get one school                     Public
POST   /api/v1/schools                — create                              Admin, Super Admin
PATCH  /api/v1/schools/{id}            — update                                Admin, Super Admin
DELETE /api/v1/schools/{id}             — soft delete                           Admin, Super Admin
```

Full Swagger descriptions on every endpoint and query parameter — visible at `/docs`.

## Tests

`tests/test_school_service.py` — 9 tests: creation without a uniqueness check (the one deliberate difference from `grades`), not-found, status update, soft delete, invalid-status schema rejection, name-length boundaries, and three dedicated phone-validation tests (valid institutional number, invalid format rejected, `None` allowed since phone is optional).

## Future improvements
- `Profile` module (schema Module 2) — once built, would read this module's repository read-only to validate `school_id` on assignment, the same pattern `topics` already uses for `subjects`/`grades`.
- A controlled vocabulary for `region`/`district` (currently free-text `VARCHAR`, per the schema as designed) — out of this sprint's scope, would need a schema change.
