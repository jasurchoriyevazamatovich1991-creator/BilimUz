# Results Module — BilimUz

Full design rationale: `docs/Sprint7_Results_Certificates_Analytics_Architecture.md` (Revision 2, approved).

## Architecture

Same 8-layer pattern. Three entities in one module (`Result`, `Statistics`, `Ranking`) — `badges`/`achievements` (also schema Module 16) are **deliberately not modeled here**, deferred per the architecture doc's Future Extensions. Reads `AttemptRepository`, `AnswerRepository` (`attempts` module) and `TestRepository` (`tests` module) — all read-only, unmodified.

## ⚠️ Scope boundary: calculation engine only, no leaderboard read endpoint

Per the approved architecture's resolved "Outstanding" decision: **`RankingService` has no "get ranking" method, and `router.py` has no `GET /results/ranking`.** Only `POST /results/ranking/recompute` exists — it computes and persists `ranking` rows, but nothing reads them back via the API yet. A public/authenticated leaderboard endpoint is explicitly future work.

## Business rules

- **One Result per attempt, forever** (idempotent `create_result` — a duplicate call returns the existing Result, never errors or creates a second one).
- **Only creatable from a finished attempt** (`status` in `submitted`/`auto_finished`) — `AttemptNotFinishedException` otherwise.
- **`is_passed` snapshotted at creation**, never recomputed later — same reasoning as the Sprint 6 timer-snapshot decision: a later edit to `tests.passing_score` must not retroactively change a historical result.
- **Statistics updated incrementally** (upsert on `(user_id, subject_id)`): `tests_taken` increments, `correct_answers`/`wrong_answers` summed from the attempt's actual answers (via `AnswerRepository`, read-only), `avg_score` recalculated as a true running average (tested explicitly — `test_statistics_running_average_is_correct`, since a naive "just overwrite with the latest score" bug is an easy mistake here).
- **Ranking is per-user-best-result**: if a user has multiple results within the same subject (multiple tests), only their highest `percentage` result counts toward ranking — an implementation decision not fully specified in the architecture doc, documented here explicitly.
- **Ranking tie-break** (approved, 3 levels): higher `percentage` → shorter attempt duration (`finish_time - start_time`, read from the linked `TestAttempt`) → earlier `finish_time`. All three levels have dedicated tests.
- **Ranking periods** (`daily`/`weekly`/`monthly`/`all_time`) are computed as rolling windows from *now* at recompute time (e.g. `weekly` = since the most recent Monday 00:00 UTC) — not fixed historical buckets. Re-running `recompute` for `weekly` next Monday naturally starts a new week's ranking.

## Database

Tables: `results`, `statistics`, `ranking` (3 of Module 16's 5 tables — `badges`/`achievements` deferred). No schema change, no migration.

## API

```
POST /api/v1/results                    — create from attempt_id, idempotent      Authenticated
GET  /api/v1/results/me                   — list my own results                       Authenticated
GET  /api/v1/results/{id}                   — get one (owner only)                        Authenticated
POST /api/v1/results/ranking/recompute        — calculation engine trigger, NO read endpoint  Admin, Super Admin
```

Full Swagger descriptions on every endpoint.

## Flow — create result

```
POST /results {attempt_id}
  → ResultService.create_result(attempt_id, user_id)
      → attempt_repo.get_by_id(attempt_id)   [read-only]
      → ownership + finished-status checks
      → idempotent return-if-exists
      → test_repo.get_by_id(attempt.test_id)  [read-only]
      → is_passed snapshotted
      → create Result
      → _update_statistics(): answer_repo.list_for_attempt() [read-only] → upsert Statistics
      → core.audit.log_action('result.created')
      → commit
```

## Flow — ranking recompute

```
POST /results/ranking/recompute {subject_id?, period}
  → RankingService.recompute(subject_id, period)
      → result_repo.list_for_subject(subject_id)   [read-only]
      → filter to the period's rolling time window
      → pick each user's single BEST result (highest percentage)
      → for each: attempt_repo.get_by_id(result.attempt_id) [read-only] for duration/completed_at
      → sort: -percentage, then duration, then completed_at
      → upsert `ranking` rows with sequential rank values
      → commit
```

## Tests

Two files, 13 tests: `test_result_service.py` (7 — wrong owner, unfinished attempt, idempotency, `is_passed` both true and null cases, ownership on read, statistics creation, running-average correctness) and `test_ranking_service.py` (5 — higher score wins, tie-break by duration, best-result-per-user selection, commit called, empty input produces zero ranked).

## Future improvements
- `GET /results/ranking` (and a public leaderboard experience) — deferred per approved scope.
- `badges`/`achievements` — deferred, schema-ready.
- Once per-test `max_attempts > 1` is introduced (flagged in `attempts/README.md`), reconsider whether ranking should use best-of-N or most-recent — current "best result" choice was made for a single-attempt world.
