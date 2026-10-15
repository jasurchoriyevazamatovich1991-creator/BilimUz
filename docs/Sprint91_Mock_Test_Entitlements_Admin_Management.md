# Sprint 91 — Mock Test Entitlements: Catalog, Access Control, and Admin Management

**Status: Implemented, unit-tested, not committed/pushed. No payment provider is integrated (see [Known Limitations](#9-known-limitations)).**

This document covers three sequential phases built in one continuous feature arc, all under the `entitlements` and `catalog` backend modules:

1. **Catalog & Entitlement data model** — `catalog_products` + `entitlements` tables (migration `0020`).
2. **Subject-Specific and Exam-Specific Mock Test Entitlements** — the `is_mock_test` flag on `tests` (migration `0021`) and live access enforcement in `AttemptService.start_attempt()`.
3. **Admin Management of Mock Test Entitlements** (this sprint's primary deliverable) — admin grant/extend/revoke APIs, the `reason` column (migration `0022`), and the admin/student UI.

Where earlier-phase details are referenced below, they have been re-verified against the current code, not assumed from memory.

---

## 1. Overview

**What it does.** An administrator can grant a user access to a **subject or exam direction** — e.g. Physics, Mathematics, IELTS, SAT, GRE — for Mock Tests. Granting one entitlement unlocks every *published* Mock Test under that direction. The admin can set a start date and an expiration date (or a duration in days), extend an entitlement that is about to lapse, reactivate one that has already expired or been revoked, and revoke access at any time. Every entitlement records who granted it, when, through what source (manual grant vs. purchase), and an optional reason. Students can see their own entitlements and expiration dates in a read-only view; they have no ability to modify them.

**Why by subject/direction, not by individual test.** The backend reuses the existing, fully generic `subjects` table (`name`/`icon`/`color` only — no school-only restriction) to represent *both* ordinary school subjects and international exam directions. A `catalog_products` row of `product_type='mock_test'` points at exactly one `subjects.id`. An entitlement for that product therefore represents "access to this direction," and the access check (`EntitlementRepository.has_active_mock_test_entitlement`) joins on `CatalogProduct.subject_id`, not on any individual `tests.id`. This means:

- An admin does not need to grant access test-by-test as new Mock Tests are published under a direction — the entitlement automatically covers every published test under that subject, present or future.
- No exam-direction name (IELTS, SAT, GRE, ...) is hardcoded anywhere in the code — an admin creates a `Subject` row for a new direction exactly as they would for a school subject, and a `CatalogProduct` row to make it grantable.

---

## 2. Business Rules

1. **One entitlement → one direction → all published Mock Tests in that direction.** Granting an entitlement for the "Physics" catalog product grants access to every `tests` row with `is_mock_test=True` and `subject_id` equal to Physics' subject id, as long as that test is `published`.
2. **Directions are isolated by construction.** The access check (`has_active_mock_test_entitlement`) filters on `CatalogProduct.product_type == 'mock_test' AND CatalogProduct.subject_id == <the test's own subject_id>` — a plain equality join, never a range or hierarchy. A Physics entitlement cannot satisfy a Mathematics, Chemistry, IELTS, SAT, or GRE lookup, and vice versa. This holds for any number of independently-created directions, not just the examples named here.
3. **Separate from grade subscriptions and courses.** `catalog_products.product_type` is also part of the join condition — a `grade_subscription` or `course` product for the exact same underlying `subjects`/`grades` row can never satisfy a `mock_test` access check, and a `mock_test` entitlement never grants grade-subscription or course access. These are three independent product types sharing one `catalog_products` table and one `entitlements` table, never conflated.
4. **Start date, expiration, and "scheduled" status.**
   - Every entitlement has a `start_date` (defaults to "now" if the admin does not supply one) and an optional `end_date` (`NULL` = no expiry).
   - If `start_date` is in the future, the entitlement does **not** yet grant access — the access-check queries filter on `start_date <= now()` in addition to the expiry check. This was a **real gap** closed as part of this sprint (see [Section 7](#7-authorization-and-security)): before this sprint, every entitlement's `start_date` was always "now" at creation, so the condition was always trivially satisfied and its absence was invisible.
   - A future-dated entitlement reports as **`scheduled`**, computed at read time (see below) — it is never a distinct value stored in the `status` database column.
5. **Expiration is lazy, not cron-driven.** There is no background job anywhere in this codebase that flips a row's stored `status` from `active` to `expired` when `end_date` passes. The access-check queries always re-verify `end_date IS NULL OR end_date > now()` regardless of the stored `status`, so an access decision is never wrong even if the stored status is stale. The stored status is lazily corrected to `expired` the next time that specific row would otherwise block a new grant for the same user/direction (see [Section 3](#duplicate-grant-handling)).
6. **Revocation is exact and non-cascading.** Revoking one entitlement updates exactly that one row (`status='revoked'`) and never touches any other entitlement for the same user, even one for a different product. There is no bulk-revoke operation anywhere in the service layer.
7. **Extension reuses the same row.** Extending an entitlement updates its `end_date` (and reactivates it to `status='active'` if it had lapsed or been revoked) rather than creating a second, conflicting row for the same user/product pair.

---

## 3. Administrator Permissions

**Authorized roles**, verified directly against the router (`require_roles("Admin", "Super Admin")` on every admin endpoint in `app/modules/entitlements/router.py`):

| Role | Can grant/extend/revoke entitlements | Can view `/entitlements/me` (own) |
|---|---|---|
| Super Admin | ✅ | ✅ |
| Admin | ✅ | ✅ |
| Moderator | ❌ | ✅ |
| Teacher | ❌ | ✅ |
| Student / Applicant | ❌ | ✅ |

**Moderator is deliberately excluded**, even though the admin panel itself is open to Moderator (`frontend/src/routes/AppRoutes.tsx`). This mirrors the same `require_roles("Admin", "Super Admin")` convention already used by the Catalog Products router and the Payments router for "admin configures something" surfaces — nothing elsewhere in this codebase grants Moderator that level of access, so it was not assumed here either.

**Granting.** `POST /entitlements/admin/grant` — targets one `user_id` + one `product_id` (a catalog product of `product_type='mock_test'`). The admin may supply a `start_date`, and either an `end_date` or a `duration_days` (not both). If the user already holds a current (active or scheduled) entitlement for that exact product, the call fails with `409 DUPLICATE_ACTIVE_ENTITLEMENT` — see the extend/reactivate workflow below.

<a id="duplicate-grant-handling"></a>**Extending / reactivating.** `POST /entitlements/admin/{entitlement_id}/extend` updates `end_date` and sets `status='active'` on the targeted row — this single endpoint both extends a currently valid entitlement and reactivates one that had expired or been revoked, so the admin never needs a separate "reactivate" action. When the grant endpoint finds a *conflicting* row (same user, same product, stored `status='active'`) whose `end_date` has already passed, it transitions that one stale row to `status='expired'` first and then proceeds with the new grant — this is what lets "grant again after expiry" succeed without violating the database's uniqueness guarantee, and without an admin ever needing to manually clean up a stale row first.

**Listing.** `GET /entitlements/admin/users/{user_id}` returns every entitlement for that user, each enriched with the direction's display name, the granting admin's name (if applicable), and a computed `effective_status`.

**Revoking.** `POST /entitlements/admin/{entitlement_id}/revoke` sets exactly that row to `status='revoked'`. Accepts an optional `reason`.

**Manual grants vs. purchases.** Every entitlement has a `source` of either `purchase` or `admin_grant`:
- A `purchase`-sourced entitlement must reference a `payment_id` (nullable FK into `payments.payments`) and has no `granted_by`.
- An `admin_grant`-sourced entitlement always has a `granted_by` (the acting admin's user id) and no `payment_id`.
- These rules are enforced by a database `CHECK` constraint (`ck_entitlements_admin_grant_has_granter`), not only in the service layer.
- **A manual grant never creates a `Payment`/`Transaction` row of any kind**, and nothing in this feature reports a manual grant as revenue — the admin-grant code path (`EntitlementService.grant_mock_test_entitlement`) never touches the `payments` module at all.

**Recorded reason and audit history.** `entitlements.reason` (migration `0022`, nullable `VARCHAR(500)`) holds the free-text justification from the **most recent** grant/extend/revoke action on that row. The full history of every action (not just the latest) is written to the platform-wide `audit_logs` table via `core/audit.py`'s `log_action()`, under these action names: `entitlement.admin_granted`, `entitlement.extended`, `entitlement.revoked`, and `entitlement.auto_expired` (the lazy-expiry transition described above). Each log entry records the acting admin's `user_id`, the affected `entitlement.id`, and a metadata payload (target user, product, dates, reason).

---

## 4. API Reference

All endpoints are mounted under the shared `/api/v1` prefix (e.g. the full path for `/entitlements/me` is `/api/v1/entitlements/me`) and return the project's standard envelope:

```json
{ "success": true, "message": "...", "data": { ... }, "errors": null }
```

On error (`success: false`), `data` is `null` and `errors` is a non-empty list of strings.

### `EntitlementOut` (shared response shape)

```json
{
  "id": "e3b0c442-...",
  "user_id": "b1946ac9-...",
  "product_id": "9e107d9d-...",
  "source": "admin_grant",
  "granted_by": "0cc175b9-...",
  "payment_id": null,
  "status": "active",
  "start_date": "2026-10-15T00:00:00Z",
  "end_date": "2027-01-13T00:00:00Z",
  "reason": "Free trial access approved by support",
  "created_at": "2026-10-15T09:00:00Z",
  "updated_at": "2026-10-15T09:00:00Z",
  "product_name": "Fizika Mock Test",
  "product_type": "mock_test",
  "subject_id": "a9993e36-...",
  "subject_name": "Fizika",
  "granted_by_name": "Ali Valiyev",
  "effective_status": "active"
}
```

`effective_status` is one of `"active" | "scheduled" | "expired" | "revoked"`, computed server-side on every read (never a value stored in the database) — see [Section 7](#7-authorization-and-security) for the exact precedence rule.

### `POST /entitlements/admin/grant`

Grants a Mock Test entitlement. **Admin, Super Admin only.**

Request body:

| Field | Type | Required | Notes |
|---|---|---|---|
| `user_id` | UUID | yes | The user to grant access to. |
| `product_id` | UUID | yes | Must reference a `catalog_products` row with `product_type='mock_test'`. |
| `start_date` | ISO 8601 datetime | no | Defaults to "now" if omitted. |
| `end_date` | ISO 8601 datetime | no | Mutually exclusive with `duration_days`. Must be after `start_date`. |
| `duration_days` | integer (1–3650) | no | Mutually exclusive with `end_date`. Relative to `start_date`, not to "now". |
| `reason` | string (≤500 chars) | no | Free-text justification. |

Example request:

```json
{
  "user_id": "b1946ac9-...",
  "product_id": "9e107d9d-...",
  "duration_days": 90,
  "reason": "Promotional access for Q4 campaign"
}
```

Success: `201 Created`, `data` is an `EntitlementOut`.

| Status | `error_code` | When |
|---|---|---|
| 401 | `INVALID_TOKEN` | Missing/invalid bearer token. |
| 403 | `FORBIDDEN` | Caller's role is not Admin/Super Admin. |
| 404 | `TARGET_USER_NOT_FOUND` | `user_id` does not exist. |
| 404 | (catalog module) `CATALOG_PRODUCT_NOT_FOUND` | `product_id` does not exist. |
| 422 | `PRODUCT_NOT_MOCK_TEST` | `product_id` refers to a `grade_subscription` or `course` product. |
| 409 | `DUPLICATE_ACTIVE_ENTITLEMENT` | The user already holds a current (active or scheduled) entitlement for this exact product — use the extend endpoint instead. |
| 422 | (validation) | `end_date`/`duration_days` both supplied, `end_date` not after `start_date`, or `duration_days` out of range. |

### `POST /entitlements/admin/{entitlement_id}/extend`

Extends or reactivates an entitlement. **Admin, Super Admin only.**

Request body — exactly one of `end_date` or `duration_days` is required (unlike grant, supplying neither is itself a validation error, since there would be nothing to change):

```json
{ "duration_days": 30, "reason": "Extended at student's request" }
```

Success: `200 OK`, `data` is the updated `EntitlementOut` (`status` is always `"active"` after a successful extend, even if the row had been `expired`/`revoked`).

| Status | `error_code` | When |
|---|---|---|
| 401 | `INVALID_TOKEN` | — |
| 403 | `FORBIDDEN` | — |
| 404 | `ENTITLEMENT_NOT_FOUND` | `entitlement_id` does not exist. |
| 422 | (validation) | Neither or both of `end_date`/`duration_days` supplied. |

### `POST /entitlements/admin/{entitlement_id}/revoke`

Revokes an entitlement. **Admin, Super Admin only.**

Request body (all optional):

```json
{ "reason": "Access granted in error" }
```

Success: `200 OK`, `data` is the updated `EntitlementOut` (`status: "revoked"`).

| Status | `error_code` | When |
|---|---|---|
| 401 | `INVALID_TOKEN` | — |
| 403 | `FORBIDDEN` | — |
| 404 | `ENTITLEMENT_NOT_FOUND` | `entitlement_id` does not exist. |

### `GET /entitlements/admin/users/{user_id}`

Lists every entitlement for a user. **Admin, Super Admin only.**

Success: `200 OK`, `data` is a JSON array of `EntitlementOut` (empty array if the user has none — not a 404).

| Status | `error_code` | When |
|---|---|---|
| 401 | `INVALID_TOKEN` | — |
| 403 | `FORBIDDEN` | — |

*(This endpoint does not itself validate that `user_id` exists — it simply returns an empty list for an unknown id, since listing is non-destructive.)*

### `GET /entitlements/me`

Lists the caller's own entitlements. **Any authenticated user.** `user_id` is taken from the bearer token only — it is never accepted as a path or body parameter, so there is no way for a user to read anyone else's entitlements through this endpoint, and no mutation exists on this endpoint at all.

Success: `200 OK`, `data` is a JSON array of `EntitlementOut`.

| Status | `error_code` | When |
|---|---|---|
| 401 | `INVALID_TOKEN` | Missing/invalid bearer token. |

### Related endpoint — Mock Test access enforcement (pre-existing phase, re-verified)

`POST /attempts/{test_id}/start` (not part of this sprint's new router, documented here for completeness since it is where an entitlement is actually consumed): for any test with `is_mock_test=True`, `AttemptService.start_attempt()` calls `EntitlementService.has_mock_test_access(user_id, test.subject_id)` and raises `403 MOCK_TEST_ACCESS_DENIED` if the caller has no current entitlement for that test's subject/direction.

---

## 5. Frontend Usage

**Admin management** — `frontend/src/pages/admin/UserDetailPage.tsx` (route: `/admin/users/:userId`). A new `UserEntitlementsPanel` component (`frontend/src/components/entitlements/UserEntitlementsPanel.tsx`) is embedded directly into this existing page — not a separate, disconnected screen. It is only rendered when the signed-in admin's role is Admin or Super Admin (gated client-side in addition to the backend's own `require_roles`, matching this page's pre-existing pattern for the role-change card). The panel:

- Lists the user's entitlements in a table (direction, status badge, start/end dates, source, granting admin).
- Shows "Cho'zish" (Extend) for any non-revoked entitlement, opening an inline form (duration preset or a custom end date, plus an optional reason).
- Shows "Bekor qilish" (Revoke) only for entitlements currently `active` or `scheduled`, behind a confirmation dialog (`ConfirmDialog`, the same reusable component used elsewhere in the admin UI, e.g. Test deletion).
- Includes a "grant new entitlement" form at the bottom: a dropdown populated from `GET /catalog/products?product_type=mock_test&status=published` (so only directions that actually have a published catalog entry can be selected — reusing the existing Catalog Products endpoints, no new backend surface needed for this), a duration selector (30/90/365 days or a custom date), an optional start date, and an optional reason.

**Student self-view** — `frontend/src/pages/student/MockTestEntitlementsPage.tsx` (route: `/student/mock-test-entitlements`, added to both the Applicant and Student sidebars in `frontend/src/utils/sidebarConfig.ts` as "Mock Test ruxsatlarim"). This page calls `GET /entitlements/me` only — it imports no mutation hooks at all, so there is no code path on this page that could grant, extend, or revoke anything, even by mistake. It renders the same direction/status/dates columns as the admin table, with no action buttons.

---

## 6. Database and Migrations

### Models

- **`catalog_products`** (`backend/app/modules/catalog/models.py`) — the purchasable/grantable unit. `product_type` is one of `grade_subscription | mock_test | course`. For `mock_test`, `subject_id` (FK → `subjects.id`) identifies the direction; `grade_id` must be `NULL`. A `CHECK` constraint (`ck_catalog_products_ref_matches_type`) enforces this exclusivity at the database level.
- **`entitlements`** (`backend/app/modules/entitlements/models.py`) — ties one `user_id` to one `catalog_products.product_id`, with `source`, optional `granted_by` / `payment_id`, `status`, `start_date`, `end_date`, and (as of this sprint) `reason`.
  - A **partial unique index** (`uq_entitlements_active_user_product`, `ON (user_id, product_id) WHERE status = 'active'`) is the database-level backstop preventing two simultaneously-active entitlements for the same user/direction, while still allowing any number of historical (expired/revoked) rows for that same pair to coexist.
  - `CHECK` constraints enforce: `source IN ('purchase','admin_grant')`, `status IN ('active','expired','revoked')`, the admin-grant/granter pairing rule, and `end_date > start_date`.
- **`tests.is_mock_test`** (`backend/app/modules/tests/models.py`) — boolean flag, `NOT NULL DEFAULT false`. A `CHECK` constraint (`ck_tests_mock_test_requires_subject`) requires `subject_id` to be set whenever this flag is true.

### Migration chain (verified against `backend/alembic/versions/`)

| Revision | Down-revision | Purpose |
|---|---|---|
| `0020_catalog_products_and_entitlements.py` | `0019` | Creates `catalog_products` and `entitlements` — fully additive, no existing table touched. |
| `0021_mock_test_direction_flag.py` | `0020` | Adds `tests.is_mock_test` (+ its `CHECK` constraint and index) — additive, defaults every existing row to `false`. |
| **`0022_entitlement_reason_column.py`** | `0021` | **This sprint.** Adds `entitlements.reason` (`VARCHAR(500)`, nullable, no default). Fully additive — one new column, nothing dropped, retyped, or backfilled. |

`0022`'s `downgrade()` simply drops the column, consistent with the other two migrations in this chain.

---

## 7. Authorization and Security

**Backend enforcement.** Every admin mutation/listing endpoint is gated by `require_roles("Admin", "Super Admin")` (`app/modules/auth/dependencies.py`), checked against `user.role.name` on the authenticated request — not inferred from the frontend. `GET /entitlements/me` uses `get_current_user` only, with the user's own id taken from the verified JWT, never from a request parameter.

**Direction isolation.** Enforced by the database join shape itself (`CatalogProduct.product_type == 'mock_test' AND CatalogProduct.subject_id == <direction>`), not by an application-level allow-list that could drift out of sync with the data — see [Section 2](#2-business-rules), rule 2.

**Scheduled entitlements and the start-date fix.** Prior to this sprint, `EntitlementRepository.has_active_grade_entitlement()` and `has_active_mock_test_entitlement()` checked `status == 'active'` and `end_date IS NULL OR end_date > now()`, but **did not** check `start_date <= now()`. This was invisible before this sprint because every entitlement's `start_date` was always "now" at creation (purchases are immediate). This sprint introduces admin-settable future `start_date`s, which would have made that gap exploitable: a "scheduled" grant would have authorized access before its own start date. **Fixed** in both methods by adding `Entitlement.start_date <= now` to the query — re-verified present in the current code.

**Attempts in progress are not retroactively affected.** Revoking or expiring an entitlement only blocks *new* attempts at `start_attempt()`. An attempt already started keeps its own pre-existing, server-authoritative `expires_at` snapshot (set once at `start_attempt()` time and never recomputed) — this sprint does not change that policy, deliberately, per the task's own instruction not to silently alter existing in-progress-attempt behavior.

**Known security limitations:**
- `GET /entitlements/admin/users/{user_id}` does not itself validate that `user_id` refers to an existing user — an admin querying a non-existent id simply receives an empty list rather than a `404`. This is a minor information-shape inconsistency with the grant endpoint (which does validate the target user), not a privilege-escalation risk, since the caller must already be Admin/Super Admin to reach either endpoint.
- As noted in [Section 9](#9-known-limitations), the actual SQL correctness of the access-check queries, the partial unique index, and the enrichment joins has not been exercised against a real PostgreSQL instance in this environment (no integration-test infrastructure was run here) — see Section 8 for exactly what *was* run.

---

## 8. Testing and Verification

This codebase's existing test strategy is **unit tests only, with the repository layer mocked** — there are no router-level (HTTP) or real-database integration tests anywhere in the project (verified by inspection before writing this sprint's tests; this is a pre-existing characteristic of the whole test suite, not something newly introduced here). This sprint's tests follow that same convention.

**Backend** — `backend/app/modules/entitlements/tests/test_entitlement_service.py` (extended this sprint with grant/extend/list/effective-status/role-rejection tests) and the pre-existing `backend/app/modules/catalog/tests/`, `backend/app/modules/attempts/tests/test_attempt_service.py` (covering the `is_mock_test` access gate from the earlier phase).

Command:

```bash
cd backend
python -m pytest app/ -q
```

Last run in this environment: **756 passed, 1 skipped.**

**Frontend** — `frontend/src/components/entitlements/UserEntitlementsPanel.test.tsx` and `frontend/src/pages/student/MockTestEntitlementsPage.test.tsx` (both new this sprint), plus the full existing suite.

Commands:

```bash
cd frontend
npx vitest run
npx tsc -b --noEmit
npx eslint <changed files>
```

Last run in this environment: **485 tests passed** (71 test files), **0 TypeScript errors**, **0 ESLint errors/warnings** on every file touched by this sprint.

**What was *not* verified:** no migration (`0020`/`0021`/`0022`) has been applied against a real PostgreSQL database in this environment — there is no Docker daemon available here, and this project has no database-integration-test harness. Migration correctness was reviewed by inspection (matching the ORM model's `__table_args__` exactly) but not executed. Do not represent any of the above test numbers as including database-level verification.

---

## 9. Known Limitations

- **No payment provider is integrated.** `backend/app/modules/payments/providers.py`'s `UnconfiguredPaymentProvider` raises `PaymentProviderNotConfiguredException` from every method — Click, Payme, Uzum, Paynet, or any other provider remains unconfigured. This feature does not change that in any way; manual admin grants exist specifically so access can be managed without a working payment integration.
- **No cron/background job exists.** Status transitions (`active` → `expired`) only happen lazily, at the moment a specific row would otherwise block a new grant (see [Section 2](#2-business-rules), rule 5). A row that is logically expired but never queried in that specific way can remain stored as `status='active'` indefinitely — this is intentional (access is still correctly denied by the date check regardless of stored status) but means the raw `status` column should never be trusted on its own; always use `effective_status` from the API response.
- **`GET /entitlements/admin/users/{user_id}` does not validate the user exists** — see [Section 7](#7-authorization-and-security).
- **No database-integration testing was performed** — see [Section 8](#8-testing-and-verification).
- **The `reason` column holds only the latest action's reason**, not a full per-action history inline on the row — the complete history is in `audit_logs`, queried separately.
- **Public catalog browsing and student-facing checkout do not exist yet** — `GET /catalog/products` remains Admin/Super Admin-only (unchanged from the earlier Catalog phase); this is unrelated to entitlement management itself but limits how a *purchase*-sourced entitlement would currently be created in practice (today, only an admin grant can create one through a UI).

---

## 10. Developer Notes

**Extending to a new product type's admin surface.** This feature's router (`entitlements/router.py`) is deliberately scoped to `product_type='mock_test'` only (enforced via `ProductNotMockTestException`). To add equivalent admin management for `grade_subscription` or `course` products, reuse `EntitlementService.create_entitlement()`/`revoke_entitlement()` (already generic across product types) rather than duplicating the grant/extend logic — only `grant_mock_test_entitlement()`'s product-type check and the catalog-product lookup are Mock-Test-specific.

**Adding a new grantable direction.** No code change is needed — create a `Subject` row (e.g. via `POST /subjects`), then a `CatalogProduct` row with `product_type='mock_test'` and that `subject_id` (via `POST /catalog/products`), then flag the relevant `tests` rows with `is_mock_test=True` and that same `subject_id`. The new direction becomes grantable and isolated automatically.

**Running tests and migrations:**

```bash
# Backend unit tests (repository-mocked, no database required)
cd backend
python -m pytest app/ -q

# Frontend unit tests, type-check, lint
cd frontend
npx vitest run
npx tsc -b --noEmit
npx eslint src

# Alembic migrations (requires a running PostgreSQL matching DATABASE_URL —
# not executed in this environment; verify independently before relying on it)
cd backend
alembic upgrade head
```

**If you add a stored "scheduled" status later:** don't. The computed-at-read-time approach (`EntitlementService._effective_status()`) was chosen deliberately to avoid needing a background job — see [Section 2](#2-business-rules), rule 4. Adding a stored enum value would require a job to transition `scheduled` → `active` at the right moment, which nothing in this codebase's architecture currently does for anything.
