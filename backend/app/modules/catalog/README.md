# Catalog Products Module — BilimUz

## Scope of this phase (Phase 1 of the Unified Learning Catalog / Grade Subscriptions plan)

This module adds **only** the `catalog_products` table and narrowly
scoped **admin-only** CRUD for it. Explicitly **not** built this phase:

- Public catalog browsing / "showing a catalog item" (spec §1) — the
  router here requires Admin/Super Admin on every endpoint.
- Checkout, payment-provider wiring, or any change to the existing
  `payments` module. `payments.Plan`/`Subscription`/`Payment`/`Transaction`
  are untouched.
- Content assignment (which Topics/Lessons/Tests belong to a product) —
  Grade-scoped content access is derived from the existing
  `Topic.grade_id`/`Test.grade_id` columns, which already exist; this
  phase does not add a separate assignment table.
- `course`-type products (IELTS/SAT/GRE) are pricing/catalog metadata
  only this phase — there is no separate `Course` catalog entity yet,
  and no content-linkage for a course product. That is deferred to a
  later phase, once the content-assignment design for courses is
  decided (a course's included tests/lessons could reuse `Test.exam_variant`
  or need a dedicated join table — not decided yet, intentionally not
  guessed at here).

## Why a new table instead of extending `payments.Plan`

`Plan` (payments module) is generic — `name`/`price`/`duration_days`/
`features` (JSONB) — with no link to any catalog entity. Extending it
with `grade_id`/`test_id` would couple the payments module (which must
stay vendor/catalog-agnostic per its own existing design) to the
catalog's specific product types. `CatalogProduct` is the new,
catalog-aware concept; `Plan` is left completely alone.

## Mock test entitlements key on subject_id (direction), not test_id

Revised by the Subject-Specific and Exam-Specific Mock Test Entitlements
feature: a `mock_test` product's ref field is `subject_id`, not a
single test. One active entitlement against a `mock_test` product
grants access to **every published mock test under that subject/exam
direction** — e.g. all published Physics mock tests, or all published
IELTS mock tests — not one test at a time. `subject_id` is reused
exactly as `grade_id` is reused for `grade_subscription`: `subjects` is
a fully generic lookup table (name/icon/color only), so an exam
direction like IELTS/SAT/GRE is just another `Subject` row an admin
creates — never a hardcoded category name anywhere in code. See
`app/modules/tests/README.md` (if present) and `tests.models.Test.is_mock_test`
for how a Test is flagged as belonging to this feature at all, and
`app/modules/entitlements/README.md` for the actual access check.

## Known simplification (documented, not hidden)

`grade_id` and `subject_id` each carry a plain `UNIQUE` constraint, not
a composite one scoped to a draft/published/archived lifecycle. This
means a grade (or a subject, for mock-test products) can only ever
have **one** `catalog_products` row of that type, total, regardless of
its `status`. Archiving a grade's or subject's product does not free
up the ability to create a *new* row for it — the correct way to
replace an archived product is to `PATCH` its `status` back to
`draft`/`published` and update its fields, not to create a second row.
A future phase may revisit this if a real need for multiple historical
product generations per grade/subject emerges.

## Database

New table: `catalog_products` (migration `0020`). See `models.py` for
the full column list and constraints (`CHECK` constraints enforce
`product_type` ∈ {`grade_subscription`, `mock_test`, `course`} and that
exactly the matching ref column — `grade_id` or `test_id` — is set).

## API

```
GET    /api/v1/catalog/products          — list/search/filter/paginate   Admin, Super Admin
GET    /api/v1/catalog/products/{id}     — get one product               Admin, Super Admin
POST   /api/v1/catalog/products          — create a product              Admin, Super Admin
PATCH  /api/v1/catalog/products/{id}     — update name/price/duration/status   Admin, Super Admin
```

`product_type` and the grade/test reference are immutable after
creation (same rule `grades`/`subjects`/`roles` already apply to their
own identity-defining fields).

## Next phase (not done here)

- Public `GET /catalog/products` (filtered to `status=published`, no
  auth) for the student-facing catalog.
- Wiring `EntitlementService.has_grade_access()` (see the
  `entitlements` module) into the actual content endpoints
  (`lessons`, `topics`, `tests`) — currently those endpoints remain
  exactly as public as they were before this migration; this phase
  does not change their behavior at all.
