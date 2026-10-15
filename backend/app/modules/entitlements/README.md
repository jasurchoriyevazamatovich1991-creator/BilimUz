# Entitlements Module — BilimUz

## Scope — Admin Management of Mock Test Entitlements (Task D, current)

This phase adds the real HTTP surface for admins to grant, extend, and
revoke **Mock Test** entitlements, plus a student-facing self-view:

- `POST /entitlements/admin/grant` — grant one user access to every
  published mock test under one subject/exam direction
  (`product_type='mock_test'` only — see `ProductNotMockTestException`).
- `POST /entitlements/admin/{id}/extend` — extends a current
  entitlement's `end_date`, or **reactivates** one that had expired or
  been revoked (same endpoint handles both — spec's "safe extension/
  reactivation workflow").
- `POST /entitlements/admin/{id}/revoke` — unchanged single-row revoke,
  now accepts an optional `reason`.
- `GET /entitlements/admin/users/{user_id}` — admin's view of one
  user's entitlements, enriched with `product_name`/`subject_name`/
  `granted_by_name`/`effective_status`.
- `GET /entitlements/me` — the same enriched shape, scoped to the
  caller's own `user_id` (from the token, never a path/body parameter),
  read-only, no admin controls.

All four admin endpoints require `require_roles("Admin", "Super Admin")`
— the same convention `catalog/router.py` and `payments/router.py`
already use for "admin configures something" surfaces. **Not**
Moderator, even though the admin *panel* itself is open to Moderator
too (`AppRoutes.tsx`) — granting/revoking access is a materially
different trust level than catalog/payments configuration, and nothing
elsewhere in this codebase gives Moderator that level of access either
(spec §3 — "do not assume every staff role has permission").

### "scheduled" status is computed, never stored

The DB enum is still exactly `active` / `expired` / `revoked`
(`ck_entitlements_status_allowed`, unchanged). "scheduled" (spec §2.8)
is computed at read time in `EntitlementService._effective_status()`
from `status` + `start_date`/`end_date` — see that method's docstring
for the exact precedence (`revoked` > date-expired > `scheduled`
(future `start_date`) > `active`). This keeps the module's "no
background jobs" architecture (nothing here runs on a clock, same as
every other lazy-transition in this codebase, e.g. attempts' lazy
auto-finish) and guarantees the value is always correct, never stale —
there is no cron job that could fail to run and leave a row saying
"scheduled" after its start_date has already passed.

### Task D bugfix: `start_date` was never checked by the access-check queries

Before this phase, every entitlement's `start_date` was always "now"
at creation (purchases are immediate), so `has_active_grade_entitlement`/
`has_active_mock_test_entitlement` omitting a `start_date <= now` filter
was invisible — the condition was always trivially true. This phase
lets an admin grant a **future-dated** ("scheduled") entitlement, so the
omission became a real bug: a scheduled grant would have authorized
access before its own start date arrived. Fixed in
`repository.py` (both methods now filter `Entitlement.start_date <= now`).

### Duplicate-grant handling: lazy expiry, not a hard block

`grant_mock_test_entitlement()` looks up the one row (if any) that
would conflict with a new grant for the same `(user_id, product_id)`
(`get_blocking_entitlement_for_grant`). If that row's `end_date` has
already passed (but its stored `status` is still `'active'` — nothing
flips it automatically), the grant call transitions that one row to
`'expired'` first, then proceeds — this is what lets "grant again after
expiry" work without ever violating the partial unique index. If the
row is genuinely still current (or scheduled), the call raises
`DuplicateActiveEntitlementException` and the admin UI points at the
existing row's "Extend" action instead of retrying a conflicting
create — never a bulk/automatic merge of the two.

### `reason` column (migration `0022`)

Additive, nullable `entitlements.reason` — free-text justification an
admin can attach to a grant/extend/revoke (spec §3 — "record ...
reason where supported by the existing schema"). `NULL` for every
pre-existing row and for every purchase-sourced entitlement (no admin
behind a purchase to give a reason). The column holds the **most
recent** action's reason only; the full history of every action is in
`audit_logs` via `log_action()` (`entitlement.admin_granted` /
`entitlement.extended` / `entitlement.revoked` / `entitlement.auto_expired`).

### Known testing-strategy gap (same as every other module here)

This codebase has **no DB-backed or router-level tests anywhere** —
every test in every module mocks the repository and exercises the
service layer only (confirmed by inspection before writing Task D's
tests). Task D's tests follow that same convention. This means the
actual SQL correctness of `start_date <= now` in the access-check
queries, the partial unique index, and the enrichment joins in
`list_for_user_with_display`/`get_with_display` is **not exercised by
an automated test** in this sandbox (no Docker daemon is available
here either — see migration `0020`'s own note). This is a pre-existing
limitation of the whole project's test strategy, not something newly
introduced by this phase, and is called out explicitly rather than
silently assumed away.

## Scope of the earlier phase (Subject-Specific and Exam-Specific Mock Test Entitlements)

- Admin grant/extend/suspend/revoke endpoints (spec §7) — **done above**.
- A student-facing `GET /entitlements/me` — **done above**.
- **Enforcement**: calling `has_grade_access()` from inside
  `lessons`/`topics`/`tests` routers to actually gate content. This is
  explicitly **not** done in this phase either — every content endpoint
  that was public before this migration remains exactly as public after
  it. See the audit's phased plan: enforcement needs its own explicit
  rollout plan (communicated cutover, not a silent flag), not a
  same-phase addition bundled in with the data model. (Mock-test access
  **is** enforced — see the section below, unchanged from the prior
  phase.)

## Why this exists instead of reusing `payments.Subscription`

Confirmed by direct repo-wide search: `Subscription` (user_id, plan_id,
start/end, status) is never read by any module outside `payments`
itself, and `Plan` has no reference to any catalog entity. There was
nothing in the existing schema an access check could key off of.
`Entitlement` ties a user to one specific `catalog_products` row in a
way the next phase's enforcement code can actually query —
`EntitlementRepository.has_active_grade_entitlement()` does the exact
join. `payments.Subscription`/`Plan`/`Payment`/`Transaction` are left
completely untouched; nothing here changes their behavior or deletes
any existing row.

## Grade isolation, by construction

`has_active_grade_entitlement(user_id, grade_id)` joins `Entitlement`
to `CatalogProduct` and filters on `CatalogProduct.grade_id == grade_id`
— plain equality, no range or hierarchy logic. A Grade 3 entitlement
can only ever satisfy a Grade 3 lookup; there is no code path that
could widen a match to Grade 2 or Grade 4. This is unit-tested
directly (`tests/test_entitlement_service.py`).

## Mock-test (subject/exam-direction) access — wired into a live endpoint

Unlike `has_grade_access()` above, `has_mock_test_access(user_id,
subject_id)` (→ `EntitlementRepository.has_active_mock_test_entitlement()`)
**is** called from a real endpoint: `AttemptService.start_attempt()`
(see `app/modules/attempts/service.py`) checks it for every test with
`is_mock_test=True` before allowing a new attempt to start. Same
equality-join construction as the grade check: a Physics entitlement
(`CatalogProduct.product_type == 'mock_test' AND
CatalogProduct.subject_id == <physics subject id>`) can never satisfy
a Mathematics or IELTS lookup, and a `course`-type or
`grade_subscription`-type entitlement for the exact same subject can
never satisfy a `mock_test` lookup either — `product_type` is part of
the join condition, not just `subject_id` (spec §1 — "Mock Test
entitlements must remain separate from grade subscriptions and
preparation courses").

Per the feature spec, this check only gates **starting a new attempt**
— an entitlement that is later revoked does not retroactively kill an
attempt already in progress (the attempt's own `expires_at`/ownership
checks, already in `attempts/service.py`, are what still govern it).

## Duplicate / invalid entitlement prevention

- Service layer: `create_entitlement()` raises
  `DuplicateActiveEntitlementException` if the user already holds an
  active entitlement for that exact product.
- DB layer (backstop for the same rule, closes the check-then-insert
  race the service-layer check alone can't): a partial `UNIQUE` index
  on `(user_id, product_id) WHERE status = 'active'`.
- `admin_grant` without a `granted_by` is rejected before any DB write
  (and the DB `CHECK` constraint `ck_entitlements_admin_grant_has_granter`
  is the backstop).
- `end_date <= start_date` is rejected by `ck_entitlements_end_after_start`.

## Database

New table: `entitlements` (migration `0020`, same migration as
`catalog_products`). Adds a nullable `payment_id` FK to the existing
`payments.payments` table — additive only, no column on `payments`
itself is touched, and every existing `Payment`/`Subscription`/
`Transaction` row is preserved exactly as it was.

## Revocation preserves unrelated entitlements, by construction

`revoke_entitlement()` updates exactly one row by its own id — there is
no bulk-revoke operation in this service. Revoking a user's Grade 3
entitlement cannot touch their IELTS-course or mock-test entitlements,
because nothing here ever writes to more than the one targeted row.
Unit-tested directly.
