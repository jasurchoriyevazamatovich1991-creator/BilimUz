# Questions Module — BilimUz

## Architecture

Same 8-layer pattern, with the `permissions`-module precedent applied at full scale: **three** cohesive entities (`Question`, `QuestionOption`, `QuestionMedia`) in one module, each with its own repository and service class inside `repository.py`/`service.py` rather than three separate top-level modules — an explicit architecture decision from `docs/Sprint6_TestEngine_Architecture.md` Section 11 ("Question options, media and answers should remain internal entities... unless future requirements justify extracting them").

`QuestionService` reads `TestRepository` read-only (referential validation) **and writes to it** via `TestRepository.increment_question_count()` — the one existing method added specifically for this reuse (built in the `tests` module, not duplicated here).

## Business rules

- **Choice-type questions need real, enforceable answer-key rules**, checked in two places by design:
  - **At creation** (`QuestionCreateRequest`'s `model_validator`, calling `validate_option_set()`): `single_choice`/`true_false` need exactly 1 correct option among ≥2 total; `multiple_choice` needs ≥1 correct among ≥2 total; `short_answer`/`essay` need none.
  - **On incremental option add/update** (`OptionService`): a narrower, always-enforceable rule — a `single_choice`/`true_false` question can never end up with **two** options marked correct, checked on every `POST .../options` and `PATCH .../options/{id}`. The full "at least 2 options, at least 1 correct" check is **not** re-verified here (it inherently can't be, mid-construction — a question with 1 option is a normal intermediate state while an author is still adding more). **Known gap, flagged not hidden**: nothing currently stops an Admin from publishing a test whose question ended up with an incomplete option set after individual edits (e.g. deleting the only correct option). A `tests`-module publish-time check would need to read `questions` — which would violate the one-directional module-dependency rule (`questions → tests`, never the reverse) — so this is deferred as a documented follow-up rather than solved by breaking that rule.
- **`tests.question_count` is always accurate** — every `create_question`/`delete_question` call updates it in the same transaction, never left to drift or require a recount query.
- **Content-authoring view vs. student view are different schemas, on purpose**: this module's `QuestionOut` includes `is_correct` on every option — correct for Admins/Teachers managing their own question bank, **catastrophically wrong** if ever reused for a student taking a test. The `attempts` module (next) has its own, separate, answer-stripped schema — never imports `QuestionOut` from here.

## Database

Tables: `questions`, `question_options`, `question_media` (Modules 12–14, `database/schema/schema_v2.sql`). All three cascade-delete from `questions.id`/`tests.id` per the existing FK definitions — no schema change this module.

## API

```
GET    /api/v1/questions                              — list (test_id/difficulty/status filter)   Authenticated
GET    /api/v1/questions/{id}                            — get one (WITH answers)                     Authenticated
POST   /api/v1/questions                                    — create (optionally with inline options)     Admin, Super Admin, Teacher
PATCH  /api/v1/questions/{id}                                — update                                        Admin, Super Admin, Teacher
DELETE /api/v1/questions/{id}                                  — soft delete, decrements question_count        Admin, Super Admin, Teacher
POST   /api/v1/questions/{id}/options                            — add an option                                  Admin, Super Admin, Teacher
PATCH  /api/v1/questions/{id}/options/{option_id}                  — update an option                                Admin, Super Admin, Teacher
DELETE /api/v1/questions/{id}/options/{option_id}                    — remove an option                                Admin, Super Admin, Teacher
POST   /api/v1/questions/{id}/media                                    — attach media                                    Admin, Super Admin, Teacher
DELETE /api/v1/questions/{id}/media/{media_id}                           — remove media                                    Admin, Super Admin, Teacher
```

**Note the access level change from `tests`/`topics`/`lessons`**: list/get require authentication (not fully public) — a question's correct answer must never be reachable by an anonymous caller, even read-only.

Full Swagger descriptions on every endpoint — visible at `/docs`.

## Flow — create question with inline options

```
Router (require_roles('Admin','Super Admin','Teacher'))
  → QuestionCreateRequest validated: option count + correct-answer count per question_type  [Pydantic]
  → service.create_question(data, actor_id)
      → test_repo.get_by_id(data.test_id)  [422 if missing]
      → build Question + append QuestionOption children (SQLAlchemy relationship, one INSERT cascade)
      → repo.create(question)
      → test_repo.increment_question_count(test_id, delta=+1)
      → core.audit.log_action('question.created')
      → repo.commit()
```

## Tests

`tests/test_question_service.py` — 16 tests across all three services: invalid test reference, successful creation with question_count increment, two schema-level cross-field validation cases (too many correct answers, too few options), essay-with-no-options allowed, not-found, delete-decrements-count, the single-choice second-correct-answer rejection (both accept and reject paths), option/media not-found cases, and a media-type schema validation case.

## Future improvements
- Resolve the "known gap" above — likely via a lightweight read-only check the `tests` module could call *into* `questions` at publish-time specifically (an intentional, narrow exception to the one-directional rule, analogous to how `roles` already reads `users` for a count) rather than the reverse dependency this module currently avoids.
- Bulk option reorder / bulk question reorder within a test, once the Admin authoring UI needs it (same pattern noted as a future improvement in the `topics` module).
