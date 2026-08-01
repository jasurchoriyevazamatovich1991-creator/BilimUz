# Attempts Module — BilimUz

The Test Engine's stateful core. Full design rationale: `docs/Sprint6_TestEngine_Architecture.md`.

## Architecture

Same 8-layer pattern. Two entities in one module (`TestAttempt`, `Answer`) — same cohesive-grouping reasoning as `questions`. Reads three other modules' repositories read-only: `TestRepository` (validate test is published, read duration/passing_score), `QuestionRepository` (snapshot content, including the one additive method `list_all_for_test()` added this sprint), `OptionRepository` (validate answer selections). Never writes to any of them.

## Business rules — the state machine

- **Start**: test must be `published` (422 otherwise); enforces a platform-wide max of **1 attempt per user per test** (`DEFAULT_MAX_ATTEMPTS` in `constants.py` — `tests.max_attempts` is not a column in the current schema, so this is a fixed constant, not per-test configurable yet; flagged as a future improvement).
- **Randomization**: question order is built **once**, at start, via `build_question_order()` (plain `random.shuffle` if `test.shuffle_questions`), and **persisted** to `test_attempts.question_order` (Alembic migration `0002`, per the approved architecture decision to store rather than compute).
- **Timer**: `expires_at` computed once at start (`start_time + test.duration`) and **persisted**, not recomputed from the test's current `duration` on every check — closes the fairness gap where an Admin editing a published test's duration could retroactively shift the deadline for attempts already in progress.
- **Lazy auto-finish**: every read/write endpoint calls `_auto_finish_if_expired()` first. No Celery, no background worker (none exists yet in the project). An attempt whose timer ran out is finalized **the next time anything touches it** — designed so a future scheduler could call the same `_finalize()` method proactively without any public API change.
- **Ownership is enforced as "not found," not "forbidden"**: `AttemptNotFoundException` covers both "doesn't exist" and "exists but isn't yours" — same resource-enumeration defense already used by `auth`/`permissions`.
- **Answer validation, in order**: attempt is yours → attempt is active → question belongs to this attempt's `question_order` → selected option belongs to that question. Any failure is a clean 422/409, never a raw DB error.
- **Scoring**: unanswered questions score zero (tested explicitly — `test_unanswered_questions_score_zero`). `is_correct` is computed and stored **at answer-save time** (efficient, avoids recomputing at submit), but never returned to the client before the attempt finishes.
- **Result availability**: `GET /{id}/result` returns `409 ResultNotAvailableException` while the attempt is still active — correctness data cannot leak before submit/auto-finish, matching the platform-wide rule already stated in `docs/API/api_blueprint.md`.

## Database

Tables: `test_attempts`, `answers` (Module 15, `database/schema/schema_v2.sql`), **plus** `expires_at` and `question_order` added by `alembic/versions/0002_add_attempt_expiry_and_question_order.py` this sprint. Neither table has `created_by`/`updated_by` — confirmed against the schema before writing the models, so `AuditMixin` is deliberately **not** used here (unlike every content-management module).

## API

```
POST   /api/v1/attempts/start              — start (422 unpublished, 409 max attempts)   Authenticated
GET    /api/v1/attempts/me                   — list my own attempts                          Authenticated
GET    /api/v1/attempts/{id}                   — resume/view (lazy auto-finish check)             Authenticated
PATCH  /api/v1/attempts/{id}/answer              — save one answer (auto-save, idempotent)            Authenticated
POST   /api/v1/attempts/{id}/submit                — finalize + score                                    Authenticated
GET    /api/v1/attempts/{id}/result                  — 409 if not finished yet                              Authenticated
```

No role restriction beyond "logged in" — unlike `tests`/`questions` (Admin/Teacher-authored content), taking a test is for any authenticated user. Full Swagger descriptions on every endpoint — visible at `/docs`.

## Flow — the full lifecycle

```
POST /attempts/start
  → test must be published, under attempt limit
  → snapshot + (optionally) shuffle all question IDs → question_order
  → compute + persist expires_at
  → status = in_progress

PATCH /attempts/{id}/answer   (called repeatedly, once per question)
  → lazy auto-finish check first
  → validate question/option belong to this attempt
  → upsert Answer, is_correct computed now (not exposed)

POST /attempts/{id}/submit
  → lazy auto-finish check first (no-op if not expired)
  → _finalize(): sum scores of correctly-answered questions, compute percentage
  → status = submitted

GET /attempts/{id}/result
  → 409 if still in_progress/paused
  → returns score, percentage, is_passed (vs. test.passing_score), correct_count
```

## Tests

Two files, 21 tests total:
- `test_attempt_validators.py` (6 tests) — pure timer/randomization functions, no DB.
- `test_attempt_service.py` (15 tests) — start (unpublished rejection, max-attempts rejection, successful snapshot), ownership (wrong owner, missing), lazy auto-finish (triggers when expired, doesn't when not), answer validation (inactive attempt, wrong question, wrong option, successful save with correctness computed), scoring (correct computation, already-finished rejection, **unanswered-questions-score-zero** — the specific rule most likely to be silently wrong if implemented carelessly), and result availability (unavailable while active, `is_passed` computed correctly).

## Known limitations (flagged, not hidden)

- **`DEFAULT_MAX_ATTEMPTS = 1` is platform-wide**, not per-test — `tests.max_attempts` doesn't exist in the current schema. A future migration would be needed for per-test configuration.
- **`get_attempt_detail()` fetches questions one at a time** (`question_repo.get_by_id()` in a loop) rather than a bulk query — chosen to avoid a second modification to the `questions` module beyond the one already required (`list_all_for_test`), per this sprint's "do not modify tests or questions unless absolutely required" instruction. Fine at typical test sizes (10–50 questions); worth revisiting with a bulk `get_by_ids()` method if profiling ever shows it matters.
- **No background scheduler** — by design for this sprint (see "Lazy auto-finish" above), not an oversight.

## Future improvements
- Per-test `max_attempts` (needs a migration).
- Bulk question fetch in `get_attempt_detail()`.
- Once Celery exists, a periodic sweep calling `_finalize()` on expired `in_progress` attempts proactively, so an abandoned attempt doesn't sit un-finalized until someone happens to view it.
- `Results` module (Sprint 7, per the existing roadmap) will read `test_attempts.score`/`percentage` to build ranking/certificates — this module deliberately does not do that itself.
