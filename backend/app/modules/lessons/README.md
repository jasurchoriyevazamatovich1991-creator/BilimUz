# Lessons Module — BilimUz

## Architecture

Same 8-layer pattern as `topics` (which it mirrors closely): `LessonService` is constructed with two repositories (`LessonRepository`, `TopicRepository`) — the latter read-only, reused unmodified for referential validation. One-directional dependency (`lessons → topics`), never the reverse.

## Business rules

- **Every lesson belongs to exactly one topic** (`topic_id`, required, cascade-delete). Referential integrity checked at the service layer (`InvalidTopicReferenceException`, 422) before it would ever reach a raw DB constraint violation.
- **A lesson must have at least one content type**: `video`, `pdf`, or `content` (rich text). Enforced in two places, deliberately:
  - **On create**: a Pydantic `model_validator` (`LessonCreateRequest`) — a lesson literally cannot be constructed empty.
  - **On update**: in `service.py`'s `_reject_if_would_leave_empty_content()` — because a `PATCH` only carries the fields being changed, the schema alone can't know whether clearing `content` would leave the lesson empty; the service merges the update onto the lesson's *current* state before checking. Swapping content types in one request (e.g. clear `content`, set `video` in the same `PATCH`) is explicitly allowed and tested (`test_update_allows_swapping_content_types`).
- **`video`/`pdf` URLs are validated** to start with `http://` or `https://` — rejects obviously malformed values before they're stored (`validators.py::validate_media_url`).
- **Soft delete** — a deleted lesson doesn't cascade-delete anything (nothing references a lesson yet in the current schema), so this is the simplest soft-delete case in the codebase.

## Database

Table: `lessons` (Module 10, `database/schema/schema_v2.sql`). FK: `topic_id → topics.id` (`ON DELETE CASCADE`). Note the asymmetry with `topics`: deleting a **topic** does *not* cascade to its lessons at the application's soft-delete layer (topics are never hard-deleted in practice) — but deleting a topic at the raw SQL level *would* cascade per the FK, since `topics` module's soft-delete doesn't touch this constraint. This mirrors real-world practice: soft delete is the *application's* deletion path; the `ON DELETE CASCADE` FK is a safety net for the rare case of a genuine hard delete (e.g. a manual DB cleanup script), not something the API ever triggers directly.

## API

```
GET    /api/v1/lessons                          — list/search/filter/paginate   Public
GET    /api/v1/lessons/{id}                       — get one                        Public
POST   /api/v1/lessons                              — create                          Admin, Super Admin, Teacher
PATCH  /api/v1/lessons/{id}                          — update                          Admin, Super Admin, Teacher
DELETE /api/v1/lessons/{id}                           — soft delete                     Admin, Super Admin, Teacher
```

Same access pattern as `topics` — Teachers author lesson content, Admins/Super Admins can too.

Full Swagger descriptions in `router.py` — visible at `/docs`.

## Flow — create lesson

```
Router (require_roles('Admin','Super Admin','Teacher'))
  → LessonCreateRequest validated: at least one of video/pdf/content present  [Pydantic, before service even runs]
  → service.create_lesson(data, actor_id)
      → topic_repo.get_by_id(data.topic_id)  [422 if missing]
      → repo.create(Lesson(...))
      → core.audit.log_action('lesson.created')
      → repo.commit()
```

## Flow — update that would empty out content (rejected)

```
PATCH /lessons/{id}  { "content": null }     ← lesson currently has ONLY content, no video/pdf
  → service.update_lesson(...)
      → _reject_if_would_leave_empty_content()
          → merges: final_video=None, final_pdf=None, final_content=None (from the update)
          → all three empty → EmptyLessonContentException (422)
```

## Tests

`tests/test_lesson_service.py` — 8 tests: invalid topic reference, successful creation, two schema-level validation cases (empty content on create, invalid URL scheme), not-found, the empty-content-on-update guard (both the rejection case and the allowed content-type-swap case), and soft delete.

## Future improvements
- File upload integration once the `uploads` module exists — `video`/`pdf` currently expect the caller to provide an already-hosted URL; direct upload-and-host would be a natural extension.
- A `duration_seconds` field for video lessons, once the frontend player needs to show progress/remaining time.
