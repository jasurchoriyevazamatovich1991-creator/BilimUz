# Topics Module — BilimUz

## Architecture

Same 8-layer pattern as every other module. One structural difference: `TopicService` is constructed with **three** repositories (`TopicRepository`, `SubjectRepository`, `GradeRepository`) instead of one — `subjects` and `grades` are read-only, reused unmodified for referential validation, the same pattern established by `roles/repository.py` reading `users.models`. This is a one-directional dependency (`topics → subjects`, `topics → grades`), never the reverse — neither `subjects` nor `grades` know `topics` exists.

## Business rules

- **Every topic belongs to a subject** (`subject_id`, required) and **optionally to a grade** (`grade_id`, nullable) — a topic can be shared across grades (e.g. a "Kasrlar" topic usable in both 5-sinf and 6-sinf) or scoped to one.
- **Referential integrity is checked at the service layer, not just the DB**: creating/updating a topic with a `subject_id` or `grade_id` that doesn't exist (or is soft-deleted) raises a clean `422 InvalidSubjectReferenceException` / `InvalidGradeReferenceException` instead of letting a raw FK-violation reach the client as a `500`.
- **`order_number`** controls display order within a subject (and grade, if set) — validated non-negative at the schema level.
- **Title is mutable** (unlike `roles`/`subjects`/`grades`'s immutable-name rule) — topics don't have anything else in the codebase referencing them by title string, so renaming is safe.
- **Soft delete does not cascade to lessons** — deleting a topic doesn't delete its lessons; they become orphaned-but-preserved, a deliberate data-safety choice (see Lessons module for the corresponding note).

## Database

Table: `topics` (Module 9, `database/schema/schema_v2.sql`). FKs: `subject_id → subjects.id` (`ON DELETE CASCADE` — if a subject is hard-deleted, its topics go with it; subjects are never hard-deleted in practice, only soft-deleted, so this is a safety net not a normal path), `grade_id → grades.id` (nullable, no cascade).

## API

```
GET    /api/v1/topics                                          — list/search/filter/paginate   Public
GET    /api/v1/topics/{id}                                       — get one                        Public
POST   /api/v1/topics                                              — create                          Admin, Super Admin, Teacher
PATCH  /api/v1/topics/{id}                                          — update                          Admin, Super Admin, Teacher
DELETE /api/v1/topics/{id}                                            — soft delete                     Admin, Super Admin, Teacher
```

Write access includes **Teacher** (not just Admin) — topics are educational content, and teachers are expected to author/maintain it, unlike `grades` (a structural lookup table Admin-only).

Full Swagger descriptions in `router.py` — visible at `/docs`.

## Flow — create topic

```
Router (require_roles('Admin','Super Admin','Teacher'))
  → service.create_topic(data, actor_id)
      → subject_repo.get_by_id(data.subject_id)  [422 if missing]
      → grade_repo.get_by_id(data.grade_id)       [422 if provided and missing]
      → repo.create(Topic(...))
      → core.audit.log_action('topic.created')
      → repo.commit()
```

## Tests

`tests/test_topic_service.py` — 8 tests: invalid subject reference, invalid grade reference, successful creation (with and without grade), not-found, invalid grade on update, soft delete, and a schema-level boundary test for negative `order_number`.

## Future improvements
- `GET /subjects/{id}/topics` convenience endpoint (currently achieved via `GET /topics?subject_id=...`, functionally equivalent but a nested route reads more naturally from the frontend's perspective).
- Bulk reorder endpoint (`PATCH /topics/reorder`, accepting a list of `{id, order_number}`) once the Admin UI needs drag-and-drop reordering — a loop of individual `PATCH` calls works today but isn't efficient for a full subject's topic list.
