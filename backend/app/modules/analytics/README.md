# Analytics Module — BilimUz

Full design rationale: `docs/Sprint7_Results_Certificates_Analytics_Architecture.md` (Revision 2, approved).

## Architecture

Same 8-layer pattern. **Fully independent module** — per the approved architecture decision, `results` never writes to `analytics`. Instead, `AnalyticsService` reads `ResultRepository` (`results` module) directly, plus, transitively, `AnswerRepository` (`attempts` module) for per-question correctness — both read-only, both unmodified. This is the module with the most external read dependencies in the codebase so far (2 other modules' repositories), but zero write dependencies in either direction.

## Why `AnswerRepository` too, not just `ResultRepository`

`results` rows carry `score`/`percentage` but not per-question correct/wrong counts — those live on `answers`, owned by `attempts`. "Calculate statistics from Results" (the approved instruction) is implemented here as **"from the Results dataset and the attempt data each Result directly references"** — the only way to populate `daily_statistics.correct_answers`/`wrong_answers` with real numbers. An earlier draft of this service briefly had a placeholder (`_subject_for()` always returning `None`) — caught and replaced before this module was considered complete; see `service.py`'s `_build_subject_cache()` for the real implementation.

## Business rules

- **`daily_statistics` is populated only by `POST /analytics/recompute/daily`** — never by a live trigger from `results`. Reads every `Result` in the given date range, resolves each result's `subject_id` via its `test_id` (cached per distinct `test_id`, not per result — avoids N+1, tested explicitly), reads each result's answers for correct/wrong counts, groups by `(user_id, subject_id, date)`.
- **Delete-and-rebuild, not incremental** — `recompute_daily` deletes existing `daily_statistics` rows in the target window before inserting fresh ones. Re-running for the same window is always correct, never double-counts (tested explicitly — `test_recompute_daily_is_delete_and_rebuild`).
- **`monthly_statistics` aggregates the module's OWN `daily_statistics`**, not `results` again — a second recompute step, deliberately separate so a monthly rebuild doesn't require re-scanning all of `results`.
- **Date range capped at 365 days** (`MAX_DATE_RANGE_DAYS`) on both the daily-activity read endpoints and the recompute request — a proactive guard against an unbounded query, addressing the "Large query risks" category flagged in the Sprint 6 audit before it could recur here.
- **"Scheduled analytics recalculation" is explicitly future work** — Sprint 7 ships the recompute *operations* only, Admin-triggered manually. Once Celery exists, the same service methods can be called from a schedule with zero change to the logic itself (same "swap the trigger, not the logic" principle as `attempts`' lazy auto-finish).

## Database

Tables: `daily_statistics`, `monthly_statistics` (Module 20, `database/schema/schema_v2.sql`). No schema change, no migration.

## API

```
GET  /api/v1/analytics/me/daily                — my daily activity, ?from=&to=&subject_id=   Authenticated
GET  /api/v1/analytics/me/monthly                 — my monthly rollup                              Authenticated
GET  /api/v1/analytics/users/{id}/daily             — any user's daily activity                       Admin, Super Admin
POST /api/v1/analytics/recompute/daily                — rebuild daily_statistics from results             Admin, Super Admin
POST /api/v1/analytics/recompute/monthly                — rebuild monthly_statistics from daily_statistics   Admin, Super Admin
```

No public endpoints — analytics is personal/administrative data, unlike `tests`/`subjects`' public catalog browsing. Full Swagger descriptions on every endpoint.

## Flow — recompute daily statistics

```
POST /analytics/recompute/daily {from, to}
  → AnalyticsService.recompute_daily(from, to)
      → result_repo.list_in_date_range(from, to)          [read-only, results module]
      → _build_subject_cache(): one test_repo.get_by_id() per DISTINCT test_id  [read-only, tests module]
      → for each result: answer_repo.list_for_attempt(result.attempt_id)        [read-only, attempts module]
      → group into (user_id, subject_id, date) buckets
      → daily_repo.delete_for_range(from, to)
      → daily_repo.create(...) for each bucket
      → commit
```

## Tests

Two files, 11 tests: `test_analytics_service.py` (7 — correct grouping, correct/wrong answer counting, delete-and-rebuild idempotency, N+1 avoidance via the subject cache, monthly aggregation, invalid month rejected, empty input produces zero buckets) and `test_analytics_validators.py` (4 — valid range, start-after-end rejected, over-max-range rejected, same-day range allowed).

## Future improvements
- **Scheduled recalculation** — wire `recompute_daily`/`recompute_monthly` to a Celery schedule once it exists.
- **Incremental recompute** — the current delete-and-rebuild is O(results in window) on every call; fine for Admin-triggered/infrequent use, would need incremental logic if it ever runs automatically and frequently.
- `avg_score` on `monthly_statistics` currently derives only from `daily_statistics.tests_taken` counts (no score data is stored at the daily granularity) — if a genuine monthly average score is needed, `daily_statistics` would need an additional score-sum column (a new migration), or monthly rollup would need to read `results` directly instead of `daily_statistics`. Flagged rather than silently approximated.
