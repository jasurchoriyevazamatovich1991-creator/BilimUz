# Task E — Integration Verification and Safe Database Validation

**Feature:** Mock Test Entitlements (Sprint 91 — Admin Management of Mock Test Entitlements)
**Companion document:** [`docs/Sprint91_Mock_Test_Entitlements_Admin_Management.md`](../Sprint91_Mock_Test_Entitlements_Admin_Management.md)
**Verification date:** 2026-10-15 (figures re-confirmed on 2026-10-16 where marked)
**Scope of this report:** what was actually executed during Task E, and what remains recommended.

> **Status in one line:** the Mock Test Entitlements migrations and queries were verified against a real, disposable PostgreSQL 16 database and a real Redis instance inside a development sandbox. Nothing in this report is a production, staging, or CI-pipeline result.

---

## 1. Overview

Before Task E, the entitlement feature reported 756 passing backend tests and 485 passing frontend tests. Those backend tests mock every repository call, so they proved the service logic but not the SQL itself. The following had never been run against a real database:

- Migrations `0020`, `0021` and `0022`.
- The join queries and the `start_date <= now < end_date` access check.
- The `CHECK` constraints and the partial unique index.

Task E closes that gap. Its scope was:

1. Verify the Alembic revision chain and apply it to a disposable test database.
2. Inspect the resulting schema (tables, constraints, indexes, columns).
3. Add database-level integration tests that run without mocked repositories.
4. Re-run existing suites to confirm no regression.
5. Trace the full path from entitlement creation to starting a mock test attempt, confirming that the backend (not only the UI) enforces access.
6. Record, without changing, how revocation affects attempts already in progress.

Out of scope, and not done: payment-provider integration, fake payment records, changes to unrelated subscription/course/grade-access behavior, and any production data access.

## 2. Environment

| Item | Value |
|---|---|
| Database engine | PostgreSQL 16 (Debian/Ubuntu package `postgresql-16`), started locally with `service postgresql start` |
| Test database | `bilimuz_test` (disposable, separate from the `bilimuz` development/production name) |
| Cache / rate limiting | Local Redis server (`redis-server`), started with `service redis-server start` |
| Python (sandbox) | 3.11; SQLAlchemy 2.0.35; `psycopg2` 2.9.9 |
| Docker | Docker CLI is installed, but **no Docker daemon is available** in the sandbox. Docker was not used. |
| Production | **Not accessed.** No production or staging database, credential or `.env` file was read or used. |

Safety gates that apply to every integration run (enforced by `backend/conftest.py`):

- `TEST_DATABASE_URL` must name a database ending in `_test`, or the run aborts.
- `TEST_REDIS_URL` must use a Redis DB index other than `0` or `1`.
- `TEST_DATABASE_URL` is never derived from `DATABASE_URL`.

Redis note: the first run of the new test file used the default Redis URL (DB index 0 on the local sandbox Redis, which held only rate-limit counters). All later runs, including the 359-test regression run and the 2026-10-16 re-confirmation, used `TEST_REDIS_URL=redis://localhost:6379/15`.

The database credentials used in the sandbox are the throwaway `postgres`/`postgres` pair that `backend/README.md` and `.github/workflows/backend-ci.yml` already document for local and CI test containers. No real secret is referenced anywhere in this report.

## 3. Migration verification

### 3.1 Revision chain

```
0019 -> 0020 -> 0021 -> 0022 (head)
```

| Revision | File | Change |
|---|---|---|
| `0020` | `0020_catalog_products_and_entitlements.py` | Creates `catalog_products` and `entitlements` |
| `0021` | `0021_mock_test_direction_flag.py` | Adds `tests.is_mock_test` and its `CHECK` constraint |
| `0022` | `0022_entitlement_reason_column.py` | Adds nullable `entitlements.reason` |

`alembic heads` reports a single head, `0022`. `alembic current` against `bilimuz_test` also reports `0022 (head)`.

### 3.2 Upgrade result

`alembic upgrade head` was run against `bilimuz_test` using `DATABASE_URL` pointed at that database. The log shows `0019 -> 0020`, `0020 -> 0021` and `0021 -> 0022` all completed without error.

The database already existed from earlier sandbox work and was at `0019`. The three new migrations were therefore applied on top of an existing schema rather than on an empty database. A from-scratch `0001 -> 0022` run is exercised by the `pg_test_database` fixture and by the CI job (see section 9), but it is not separately recorded as a Task E result.

Only the upgrade path was exercised. The `downgrade()` functions were not run.

### 3.3 Schema inspected with `psql`

The live schema was compared against the migration source.

**`catalog_products`**
- Check constraints: `ck_catalog_products_product_type_allowed`, `ck_catalog_products_status_allowed`, `ck_catalog_products_ref_matches_type`, `ck_catalog_products_price_non_negative`, `ck_catalog_products_duration_positive`.
- `ck_catalog_products_ref_matches_type` requires a `mock_test` product to have `subject_id` set and `grade_id` NULL.
- `grade_id` and `subject_id` each carry a plain `UNIQUE` constraint: at most one catalog product per subject or direction.

**`entitlements`**
- Check constraints: `ck_entitlements_source_allowed`, `ck_entitlements_status_allowed`, `ck_entitlements_admin_grant_has_granter`, `ck_entitlements_end_after_start`.
- Partial unique index `uq_entitlements_active_user_product` on `(user_id, product_id) WHERE status = 'active'`.
- `reason` is `VARCHAR(500)`, nullable.
- Foreign keys: `user_id`, `granted_by` → `users`; `product_id` → `catalog_products`; `payment_id` → `payments`.

**`tests`**
- `is_mock_test` is `boolean NOT NULL DEFAULT false`, with index `ix_tests_is_mock_test`.
- `ck_tests_mock_test_requires_subject`: `is_mock_test = false OR subject_id IS NOT NULL`.

### 3.4 Result

The schema produced by the migrations matches the migration source and the ORM models. No discrepancy was found, and no production source or migration file needed changing.

## 4. Database integration tests

**New file:** `backend/tests/integration/test_sprint91_mock_test_entitlements_integration.py`

It follows the existing convention in `backend/tests/integration/`: the `pg_session` and `client` fixtures from `backend/conftest.py`, real rows, and no mocked repositories. Each test is rolled back on teardown. Two layers are covered:

- **Service/repository level (no HTTP):** rows are created through the ORM and services against real PostgreSQL.
- **HTTP level:** requests go through the real FastAPI app with real JWT login and real role checks.

**Result: 21 tests, 21 passed** (first run 2026-10-15; re-confirmed 2026-10-16 with `TEST_REDIS_URL` DB 15).

| # | Behavior covered | Test |
|---|---|---|
| 1 | Access is recognized while `start_date <= now < end_date` | `test_active_entitlement_recognized_exactly_on_start_le_now_lt_end` |
| 2 | A future `start_date` (scheduled) does not grant access | `test_scheduled_entitlement_does_not_grant_premature_access` |
| 3 | An expired entitlement blocks a new attempt, even though the stored `status` is still `active` | `test_expired_entitlement_cannot_authorize_new_attempt` |
| 4 | One entitlement covers every published mock test of its own subject | `test_entitlement_covers_every_published_mock_test_under_its_subject` |
| 5 | An entitlement for one subject does not authorize another subject | `test_entitlement_for_one_subject_does_not_authorize_another_subject` |
| 6 | A duplicate active grant is rejected by the service and by the DB partial unique index (`IntegrityError`) | `test_duplicate_active_grant_is_rejected_by_service_and_by_db_constraint` |
| 7 | A date-expired row is lazily set to `expired`, then a new grant succeeds | `test_duplicate_grant_is_allowed_again_once_prior_entitlement_is_date_expired` |
| 8 | Grant, extend and revoke persist across fresh reads | `test_grant_extend_revoke_persist_correctly_across_fresh_reads` |
| 9 | Revoking one entitlement leaves an unrelated one untouched | `test_revoking_one_entitlement_does_not_modify_an_unrelated_entitlement` |
| 10 | Admin endpoint rejects an unauthenticated request (401/403) | `test_admin_endpoints_reject_unauthenticated_requests` |
| 11 | Admin endpoint rejects a Student JWT with 403 | `test_admin_endpoints_reject_non_admin_role` |
| 12 | Full admin grant → extend → revoke over HTTP | `test_admin_grant_extend_revoke_full_http_flow` |
| 13 | Grant for a non-existent user returns 404 | `test_grant_for_nonexistent_user_returns_404` |
| 14 | Grant against a non-`mock_test` product returns 422 | `test_grant_against_non_mock_test_product_returns_422` |
| 15 | Duplicate grant over HTTP returns 409 | `test_grant_duplicate_via_http_returns_409` |
| 16 | `/entitlements/me` returns only the caller's own rows | `test_entitlements_me_returns_only_the_callers_own_rows` |
| 17 | `/entitlements/me` rejects unauthenticated requests | `test_entitlements_me_rejects_unauthenticated_requests` |
| 18 | `/attempts/start` without an entitlement returns 403 | `test_backend_blocks_attempt_start_without_entitlement_via_real_http_call` |
| 19 | Admin grants, then the student starts an attempt (201) | `test_end_to_end_grant_then_start_attempt_via_real_http_call` |
| 20 | `expires_at` is unchanged when the attempt is re-fetched | `test_attempt_deadline_persists_across_a_fresh_refetch` |
| 21 | Revoking does not affect an attempt already in progress, and blocks a new one | `test_revoking_entitlement_does_not_affect_an_already_in_progress_attempt` |

Two points on the first run:

- The first run produced 8 failures, all caused by Redis not running, because login needs Redis for rate limiting. The services were started and 20 of 21 passed.
- The remaining failure was a wrong assertion in the test itself (the response `message` was correct). The assertion was fixed in the test file, with no production change.

## 5. Regression tests

| Suite | Command (from the directory shown) | Result |
|---|---|---|
| Backend integration (real PostgreSQL + Redis) | `pytest tests/integration/` in `backend/` | **359 passed** (338 existing + 21 new); re-confirmed 2026-10-16 |
| Backend unit (mocked) | `python -m pytest app/ -q` in `backend/`, with `TEST_*` variables unset | **756 passed, 1 skipped** |
| Frontend tests | `npx vitest run` in `frontend/` | **485 passed** in 71 files |
| TypeScript | `npx tsc -b --noEmit` in `frontend/` | **0 errors** |
| ESLint | `npx eslint . --max-warnings=0` in `frontend/` | **0 errors, 5 warnings** |

Notes:

- The 359 count is the number of tests collected in `tests/integration/` (42 files). It equals the 338 recorded in `README_SPRINT_88.md` plus the 21 new tests.
- The 1 skipped unit test is `app/core/tests/test_redis_test_isolation.py:69`. Its skip message reads "TEST_REDIS_URL not set — redirect is a no-op by design". That is expected when `TEST_REDIS_URL` is unset, not a failure.
- The frontend, TypeScript and ESLint figures come from the Task E run on 2026-10-15. They were not re-run on 2026-10-16, and no frontend file was changed in Task E.
- `--max-warnings=0` makes the ESLint command exit non-zero when warnings exist, even with 0 errors. The project's own lint script, `npm run lint`, is plain `eslint .` (no `--max-warnings`) and is what the frontend CI workflow runs.

### The five ESLint warnings

None of the five files was modified by Task E.

| File | Line | Rule | Description |
|---|---|---|---|
| `src/pages/admin/LessonFormPage.tsx` | 71 | `react-hooks/exhaustive-deps` | `useEffect` is missing dependency `basePath` |
| `src/pages/admin/QuestionFormPage.tsx` | 146 | `react-hooks/exhaustive-deps` | `useEffect` is missing dependency `basePath` |
| `src/pages/admin/TestFormPage.tsx` | 74 | `react-hooks/exhaustive-deps` | `useEffect` is missing dependency `basePath` |
| `src/pages/admin/TopicFormPage.tsx` | 64 | `react-hooks/exhaustive-deps` | `useEffect` is missing dependency `basePath` |
| `src/pages/student/AttemptPage.tsx` | 99 | unused directive | Unused `eslint-disable` directive |

Where they come from, checked against `git diff`:

- **`TestFormPage.tsx`:** the flagged `useEffect` is not one of the lines added by the Mock Test feature work in this file.
- **`AttemptPage.tsx`:** it carries other uncommitted changes (285 insertions, 49 deletions) from earlier sprints. Whether this specific directive predates those changes was not isolated.

## 6. End-to-end verification

These flows ran over real HTTP, through the real router, dependency wiring, service and repository, against real PostgreSQL:

1. **Admin grant.** A Super Admin logs in and calls `POST /api/v1/entitlements/admin/grant`. The response is 201, with `effective_status = "active"` and the subject name populated.
2. **Student attempt start.** The student logs in and calls `POST /api/v1/attempts/start`. The response is 201 (test 19).
3. **Unauthorized start blocked.** A student with a valid JWT but no entitlement calls `POST /api/v1/attempts/start` for a published mock test. The response is **HTTP 403**, so the backend enforces access, not only the UI (test 18).
4. **Role enforcement.** A Student JWT calling `/entitlements/admin/grant` gets 403; no token gets 401/403 (tests 10 and 11).
5. **User isolation.** Two students each hold an entitlement for the same product. `GET /api/v1/entitlements/me` for the first returns exactly one row, with that student's `user_id` (test 16).
6. **Deadline persistence.** `expires_at` computed at `start_attempt()` is identical when the attempt is re-fetched (test 20). This is a service-level re-read in the same session, not a browser reload.

**Frontend (code inspection plus the existing 485-test suite).** These source files were read and checked against the requirements; no new frontend tests were added:

- `UserEntitlementsPanel.tsx`
- `MockTestEntitlementsPage.tsx`
- `useEntitlements.ts`
- `api/client.ts`

What was confirmed:

- The grant form sends `product_id` and either `duration_days` or `end_date`.
- The grant picker lists only published `mock_test` products.
- Revoke goes through a `ConfirmDialog`, then refetches the list.
- Failed requests surface the backend's own `message` in a toast.
- Admin controls render only for Admin and Super Admin.
- The student page imports no mutation hooks.

The existing `UserEntitlementsPanel.test.tsx` (8 tests) and `MockTestEntitlementsPage.test.tsx` (4 tests) cover these behaviors with a mocked API layer. A real browser session against a running backend was **not** performed.

## 7. Files changed

| File | Change | Reason |
|---|---|---|
| `backend/tests/integration/test_sprint91_mock_test_entitlements_integration.py` | **New** (untracked) | The 21 database-level integration tests |
| `docs/reports/task-e-mock-test-entitlements-verification.md` | **New** (untracked) | This report |

**No production source files were modified during Task E.** This was checked by file modification time. The entitlements module sources were last modified at 20:46 on 2026-10-15, before Task E began. After 21:00 that day, the only changes were the new test file (21:36) and the Sprint 91 documentation file (21:02), which was written before Task E started. Frontend and `alembic/` files show no changes in that window. This is a timestamp check, not a diff against a baseline, because the earlier feature work is itself uncommitted.

Not changed: no migration, model, service, router or frontend file; no CI workflow; no `.env` file.

## 8. Known behavior and limitations

1. **Revocation affects new attempts only.** `AttemptService.start_attempt()` is the only place in `app/modules/attempts/service.py` that consults `entitlement_service`. `get_attempt`, `submit_attempt`, `save_answer` and `submit_module` do not. After revocation:
   - A new attempt is blocked with 403.
   - An attempt already in progress stays readable and completable.

   Test 21 asserts both halves. This is the shipped behavior; it was documented, not changed. If revocation should terminate in-progress attempts, that is a separate product decision.
2. **Entitlement changes do not modify existing attempts.** `expires_at` is computed once at attempt start and is not recalculated.
3. **"Scheduled" is computed, not stored.** `effective_status` is derived at read time. Stored `status` is only `active`, `expired` or `revoked`, and no background job transitions rows. Expired rows are normalized lazily when a conflicting grant is attempted.
4. **One catalog product per subject.** `catalog_products.subject_id` is `UNIQUE`, so each subject or direction can have at most one catalog product. Archiving a product does not free the subject for a replacement row.
5. **Production CI validation is still recommended.** `.github/workflows/backend-ci.yml` defines an isolated PostgreSQL 16 + Redis 7 job (Python 3.13, `alembic upgrade head`, then `pytest tests/integration/ -v`) that would pick up the new test file. **That workflow was not run as part of Task E.** The sandbox used Python 3.11 with locally installed services, not the CI containers.
6. **Payment providers are not configured.** Task E added no payment-provider integration and created no payment records. `entitlements.payment_id` stays NULL for admin grants. Paid purchase flows are not verified by this report.
7. **Migration downgrades were not exercised.** Only the upgrade path was run.
8. **No concurrency test for entitlement grants.** The partial unique index backs duplicate safety, but a two-simultaneous-grants race was not tested.

## 9. Commands to reproduce verification

The commands below are taken from `backend/README.md`, `.github/workflows/backend-ci.yml`, `.github/workflows/frontend-ci.yml` and the test file. They assume PostgreSQL 16 and Redis are running locally and that `bilimuz_test` is a disposable database. The credentials shown are the placeholder pair the project documents for test databases; substitute your own if your setup differs.

**Backend: apply migrations to the test database** (from `backend/`)

```bash
PGPASSWORD=postgres psql -h localhost -U postgres -c "CREATE DATABASE bilimuz_test;"   # skip if it already exists
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/bilimuz_test alembic heads
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/bilimuz_test alembic upgrade head
```

**Backend: new integration tests** (from `backend/`)

```bash
TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/bilimuz_test \
TEST_REDIS_URL=redis://localhost:6379/15 \
    python -m pytest tests/integration/test_sprint91_mock_test_entitlements_integration.py -v
```

**Backend: full integration suite** (from `backend/`)

```bash
TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/bilimuz_test \
TEST_REDIS_URL=redis://localhost:6379/15 \
    python -m pytest tests/integration/ -q
```

**Backend: unit suite** (from `backend/`; no database or Redis needed)

```bash
python -m pytest app/ -q
```

`backend/README.md` documents `python -m pytest app/ scripts/ -q`. The 756/1 figure in this report is for `app/` alone.

**Frontend** (from `frontend/`; matches `frontend-ci.yml`)

```bash
npm run test
npx tsc -b --noEmit
npm run lint
```

**Inspect the schema** (optional)

```bash
PGPASSWORD=postgres psql -h localhost -U postgres -d bilimuz_test -c "\d catalog_products"
PGPASSWORD=postgres psql -h localhost -U postgres -d bilimuz_test -c "\d entitlements"
PGPASSWORD=postgres psql -h localhost -U postgres -d bilimuz_test -c "\d tests"
```

Never point `TEST_DATABASE_URL` at a development or production database. `backend/conftest.py` refuses names that do not end in `_test`.

## 10. Production-readiness checklist

None of these items is claimed as done.

- [ ] Run `.github/workflows/backend-ci.yml` on GitHub Actions (isolated PostgreSQL 16 + Redis 7, Python 3.13) and confirm the new integration tests pass there.
- [ ] Run `.github/workflows/frontend-ci.yml` and confirm test, type-check, lint and build all pass.
- [ ] Apply `0020 -> 0022` to a staging database that holds a production-like snapshot, and verify timing and locking on realistic table sizes.
- [ ] Back up the production database before applying migrations, and rehearse the `0022 -> 0019` downgrade path.
- [ ] Decide whether revoking an entitlement should end in-progress attempts. If so, specify and test it.
- [ ] Add a concurrency test for simultaneous grants, or accept the partial unique index as the guard.
- [ ] Clear or accept the five pre-existing ESLint warnings.
- [ ] Exercise the admin and student screens in a browser against a running backend.
- [ ] Decide the payment path for paid mock-test purchases, and test it with a real provider in sandbox mode.
- [ ] Confirm which roles may grant entitlements. Today it is Admin and Super Admin only; Moderator is excluded.
- [ ] Review audit-log output for `entitlement.admin_granted`, `entitlement.extended`, `entitlement.revoked` and `entitlement.auto_expired` in staging.
- [ ] Commit and push the feature work (this was not done as part of Task E).
