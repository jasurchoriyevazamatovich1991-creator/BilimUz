# Learning Centers Module — BilimUz

Full design rationale: `docs/Sprint10_Schools_LearningCenters_Architecture.md` (approved).

## Architecture

Same 8-layer pattern. Structurally near-identical to `schools` (built this same sprint) — kept as a **separate module**, not merged, matching the schema's own module boundary (Module 6 vs Module 5) and the `grades`/`topics`/`lessons` precedent of not collapsing similarly-shaped entities into one module.

## ⚠️ Known scope boundary: no consumer yet

Same situation as `schools`: `profiles.learning_center_id` (schema Module 2) references this table, but `profiles` has never been implemented. This module ships as a complete, standalone catalog this sprint — assignment deferred to a future `Profile` sprint (approved decision).

## Business rules

- **`name` is NOT required to be unique** — same reasoning as `schools`: the schema has no `UNIQUE` constraint, and two different learning centers in different cities may share a name.
- **Phone validation** — same broader institutional format as `schools` (approved decision 2): `+998` + 9 digits, not restricted to mobile-operator prefixes.
- **The phone validator is defined locally in this module**, not imported from `schools` or `auth` — deliberately duplicated rather than shared, to keep both modules independently zero-dependency (matching the architecture doc's stated design, and the same reasoning `grades`/`topics`/`lessons` already established for not sharing code just because the shape is similar).
- **`owner_name` is optional** but validated for length when provided (2–255 chars) — represents the center's registered owner/director, common for privately-run learning centers.
- **Soft delete only** — `deleted_at` + `status='archived'`.

## Database

Table: `learning_centers` (Module 6, `database/schema/schema_v2.sql`). No schema change, no migration.

## API

```
GET    /api/v1/learning-centers              — list/search/filter/paginate      Public
GET    /api/v1/learning-centers/{id}           — get one                            Public
POST   /api/v1/learning-centers                 — create                              Admin, Super Admin
PATCH  /api/v1/learning-centers/{id}              — update                                Admin, Super Admin
DELETE /api/v1/learning-centers/{id}               — soft delete                           Admin, Super Admin
```

**Note the URL/module-name split**: the URL uses a hyphen (`learning-centers`, REST convention) while the Python module and database table use snake_case (`learning_centers`, approved decision 3, matching the schema exactly) — the same pattern already used for `certificate-templates` (URL) vs. `certificate_templates` (table).

Full Swagger descriptions on every endpoint and query parameter.

## Tests

`tests/test_learning_center_service.py` — 10 tests: creation without a uniqueness check, not-found, status update, soft delete, invalid-status rejection, name-length boundaries, phone validation (valid/invalid), and two `owner_name`-specific tests (optional, length-validated when provided).

## Future improvements
- `Profile` module — once built, would read this module's repository read-only to validate `learning_center_id` on assignment.
