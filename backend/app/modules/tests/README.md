# Tests Module — BilimUz

## Architecture

Same 8-layer pattern as every module. `TestService` reads three other repositories (`SubjectRepository`, `GradeRepository`, `TopicRepository`) read-only for referential validation — same established pattern as `topics`. This module owns **test definitions only** — the taking-experience lives in the `attempts` module (Sprint 6, next), which reads this module's repository read-only, never the reverse.

## Business rules

- **`subject_id`, `grade_id`, `topic_id` are all optional** — a test can exist unscoped (e.g. a general aptitude test), or scoped to any combination. Whichever are provided are validated to reference real, non-deleted rows (422 `InvalidTestReferenceException`, not a raw DB error).
- **Status is a strict state machine**: `draft → published → archived`, enforced by `ALLOWED_STATUS_TRANSITIONS` in `constants.py`. No skipping states, no going backward — an `archived` test is terminal. Publishing has its own endpoint (`POST /{id}/publish`) rather than being a value in the generic `PATCH`, because it's a meaningful business event (audit-logged as `test.published`, distinct from `test.updated`), not a data edit.
- **A test cannot be published with zero questions** (`CannotPublishEmptyTestException`) — `question_count` is maintained by the `questions` module via `TestRepository.increment_question_count()` (shared, not duplicated logic), so this check is always accurate without a `COUNT(*)` query.
- **`duration`**: 1–480 minutes. **`passing_score`**: 0–100 (percentage), optional (a test can exist with no pass/fail threshold, e.g. a diagnostic).

## Database

Table: `tests` (Module 11, `database/schema/schema_v2.sql`). No schema change this module — `difficulty` and `status` are Postgres native enum types in the DB (`difficulty_level`, `test_status`), mapped as `String` columns in the SQLAlchemy model, consistent with how `users.status` was already handled in Sprint 1 (see `app/modules/users/models.py`).

## API

```
GET    /api/v1/tests                 — list/search/filter/paginate   Public
GET    /api/v1/tests/{id}              — get one                        Public
POST   /api/v1/tests                    — create (starts as 'draft')       Admin, Super Admin, Teacher
PATCH  /api/v1/tests/{id}                — update metadata                    Admin, Super Admin, Teacher
POST   /api/v1/tests/{id}/publish         — draft → published                   Admin, Super Admin, Teacher
DELETE /api/v1/tests/{id}                  — soft delete                          Admin, Super Admin, Teacher
```

Full Swagger descriptions (`summary` + `description`) on every endpoint — visible at `/docs`.

## Flow — publish a test

```
Router (require_roles('Admin','Super Admin','Teacher'))
  → service.publish_test(test_id, actor_id)
      → get_test(test_id)  [404 if missing]
      → is_valid_status_transition(test.status, 'published')  [409 if not allowed]
      → test.question_count >= 1  [422 if empty]
      → repo.update({status: 'published'})
      → core.audit.log_action('test.published')
      → repo.commit()
```

## Tests

`tests/test_test_service.py` — 10 tests: invalid subject reference, creation with no references (all optional), not-found, publish-empty rejection, publish-from-archived rejection, successful publish, invalid grade on update, soft delete, and two schema-level boundary tests (duration, passing_score ranges).

## Future improvements
- `starts_at`/`ends_at` scheduling window (mentioned in the original API blueprint) — not in the current schema, would need a migration if required.
- Once `permissions` has seeded codes for this module, `require_roles(...)` should migrate to `require_permission("tests.manage")` per `docs/ADR/ADR-006-Use-RBAC.md`.
