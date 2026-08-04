# Sprint 12 — Architecture Design: Audit Logs, System Logs

**Status: DESIGN ONLY — no code written, no repository files modified, no ZIP, no git.**

## Architecture Freeze — compliance statement

| Rule | Compliance |
|---|---|
| No new architectural layers | ✅ Same 8-layer pattern for both modules — with one explicitly-flagged special case for `audit_logs/models.py` (see Q1 below), not a new layer, a documented reuse. |
| No parallel implementations | ✅ `audit_logs` does **not** reimplement `log_action()` — it reads the exact same `AuditLog` table `core/audit.py` already writes to. Building a second write path would be the parallel-implementation mistake this rule exists to prevent. |
| No temporary or legacy code | ✅ Everything specified ships as final, real capability — no stubs. |
| Existing architecture exactly | ✅ Router → Service → Repository → Database, unchanged. `core/audit.py` and `core/logging.py` are **not modified** — both stay exactly as they are. |
| Work only inside approved module structure | ✅ Two new folders under `app/modules/`. Zero changes to `core/`. |
| No placeholders / fake implementations | ✅ N/A — plain read/write CRUD, no vendor boundary. |
| No TODOs except documented future features | ✅ The `core/logging.py` → `system_logs` wiring gap (below) is a named Future Extension, not a code TODO. |

---

## 1. How is the existing audit system (`core/audit.py`) currently used?

Investigated directly (not assumed): `log_action(db, action, user_id, entity_type, entity_id, ip_address, metadata)` is called from **34 call sites across 20 modules** (`auth`, `users`, `roles`, `grades`, `topics`, `lessons`, `tests`, `questions`, `attempts`, `results`, `certificates`, `settings`, `uploads`, `notifications`, `ai`, `payments`, `schools`, `learning_centers`, `profiles`, `permissions`) — it is the single, consistently-used write path for "something happened" events platform-wide, exactly as designed in Sprint 1.

**What's missing**: there is no repository, service, or router anywhere that *reads* `audit_logs` back. An Admin cannot currently answer "what did user X do last week" through the API — the data is being captured correctly, just never surfaced.

`system_logs` is a different situation entirely: **nothing writes to it**. `core/logging.py` configures Python's standard `logging` module to write structured JSON to **stdout only** — it has never touched the `system_logs` table. The table has existed in the schema since the baseline migration (`0001`) but has zero producers and zero consumers today.

---

## 2. Is a new module needed, or should the existing audit capability be extended?

**Both — but differently for each table**, per the investigation above:

- **`audit_logs`**: the **write** side is complete and correct in `core/` — do not touch it, do not duplicate it. What's needed is a **read-only** module built on top of the existing table.
- **`system_logs`**: needs both a **write** capability (currently doesn't exist at all) and a **read** capability — a genuinely new module, not an extension of anything.

Two separate modules, matching the schema's own module boundary (24 vs. 25) — same precedent as keeping `schools`/`learning_centers` separate despite structural similarity (Sprint 10).

---

## Module A — `app/modules/audit_logs/`

### Database impact
**No new tables, no migration.** Reads the existing `audit_logs` table (Module 24) via the existing `AuditLog` model already defined in `core/audit.py` — **not redefined here** (see Outstanding Decision #1 for how this is represented in this module's `models.py`).

### API design

| Method | Path | Purpose | Auth |
|---|---|---|---|
| GET | `/audit-logs` | List/filter (`user_id`, `action`, `entity_type`, `date_from`, `date_to`), paginated | Super Admin |
| GET | `/audit-logs/{id}` | Get one entry | Super Admin |

**Read-only, by design** — no `POST`/`PATCH`/`DELETE`. This module never writes to `audit_logs`; every other module already does that via `core.audit.log_action()`, unchanged.

### Repository layer
`AuditLogRepository`: `get_by_id`, `list` (filter by `user_id`/`action`/`entity_type`/date range, paginate) — imports `AuditLog` from `app.core.audit`, does not redefine it.

### Service layer
`AuditLogService`: thin read wrapper — no business rules beyond pagination/filtering, since this data is already correct by construction (written by the same trusted `log_action()` every module uses).

### Dependencies
None on other business modules. Reads the `AuditLog` model from `core/` (already-established precedent: every module already depends on `core/` for shared infrastructure — this is the first module to read a *model* from `core/` rather than just calling a function, flagged explicitly in Outstanding Decision #1).

### Security
This is the most sensitive read surface in the platform — it can reveal every user's actions across every module. **Super Admin only**, no exceptions, no Admin tier (stricter than the `settings` module's already-strict pattern, because `settings` protects infrastructure credentials while `audit_logs` protects behavioral data about every real person on the platform).

### Validation rules
Date range capped (same proactive guard as `analytics`'s `MAX_DATE_RANGE_DAYS`) — an unbounded `audit_logs` query across the whole table's history would be the platform's largest possible read, given 34 write call sites accumulating indefinitely.

### Test strategy
~10 tests: list with each filter type, pagination, date-range cap enforcement, not-found, RBAC (Super-Admin-only enforcement, no Admin-tier access).

---

## Module B — `app/modules/system_logs/`

### Database impact
**No new tables, no migration.** `system_logs` (Module 25) already exists in the baseline. This module defines its **own** `SystemLog` model (unlike `audit_logs`) — there is no existing model anywhere to reuse, since nothing has ever touched this table.

### API design

| Method | Path | Purpose | Auth |
|---|---|---|---|
| GET | `/system-logs` | List/filter (`level`, `source`, date range), paginated | Super Admin |
| GET | `/system-logs/{id}` | Get one entry | Super Admin |
| POST | `/system-logs` | Record a system-level event | Super Admin |

**Real write capability this sprint** — `POST` genuinely inserts a row, no honest-refusal pattern needed here (unlike Sprint 8/9's provider interfaces) since there's no external vendor involved, just a database write.

### Repository layer
`SystemLogRepository`: `get_by_id`, `list` (filter by `level`/`source`/date range, paginate), `create`.

### Service layer
`SystemLogService`: `create_log(level, source, message, context)` — importable as a plain Python function/method (same calling convention as `core.audit.log_action()`) so a **future** sprint can wire `core/logging.py` to call it on WARNING+ events without needing to go through HTTP. **This wiring is explicitly NOT done this sprint** — `core/logging.py` is not modified (Architecture Freeze: don't touch stable core infrastructure without a specific, approved reason).

### Dependencies
None on other business modules.

### Security
Same Super Admin-only tier as `audit_logs` — system-level error/warning messages can leak internal details (stack traces, file paths) that shouldn't be broadly visible, consistent with the platform-wide rule that internal errors never reach a client response.

### Validation rules
`level` restricted to `info | warning | error | critical` (matches the schema comment). `message`: non-empty, reasonable max length (prevent an unbounded log message). Date range cap on list queries, same as `audit_logs`.

### Test strategy
~12 tests: create (each level), list with each filter, pagination, date-range cap, invalid level rejected, not-found, RBAC enforcement.

---

## Estimates

| | Estimate |
|---|---|
| Migrations | **0** — both tables already exist in baseline `0001` |
| Endpoints | **5** (`audit_logs`: 2, `system_logs`: 3) |
| Unit tests | **~22** (10 + 12) |
| Files | **~22** (11 per module — `audit_logs` has a smaller `models.py`, `system_logs` has a normal one) |

---

## Risks

| Risk | Severity |
|---|---|
| **`audit_logs` becomes a very large table over time** (34 write call sites, growing) — list queries need the date-range cap and pagination to stay safe; no archival/retention policy exists yet. | Medium |
| **`system_logs` has zero producers until `core/logging.py` is wired to it** (deferred) — the module is fully real and testable, but will show an empty list in production until that future integration happens. Same "framework, not yet fully integrated" honesty as Sprint 8/9. | Low — explicitly flagged, not hidden |
| **`audit_logs/models.py` reusing a `core/`-defined model is a new pattern** for this codebase — every other module owns its model. If done inconsistently later, could confuse future contributors about where a model "belongs." | Low, mitigated by Outstanding Decision #1 being resolved explicitly now |

---

## Definition of Done
- Same 8-layer pattern (with the one documented exception), `py_compile`, 0 circular imports, full Swagger, README/CHANGELOG updates.
- `core/audit.py` and `core/logging.py` verified untouched (grep-checked) as part of validation.
- All Outstanding Decisions below resolved before implementation starts.

---

## Project Impact Analysis

**Does Sprint 12 introduce architectural changes?** One genuinely new pattern: `audit_logs` reading a model defined in `core/` rather than owning its own — flagged as Outstanding Decision #1, not silently introduced. Everything else is the same Router → Service → Repository shape as every prior sprint.

**Does it increase coupling?** Minimally. `audit_logs` gains a dependency on `core.audit` (reading `AuditLog`) beyond the shared-infrastructure dependency every module already has. `system_logs` has zero dependencies, the simplest possible module (matching `uploads`' independence level).

**Are Audit Logs and System Logs independent of each other?** Yes, completely — different tables, no shared code, no cross-reads.

**Future extension points?** `core/logging.py` → `SystemLogService.create_log()` wiring (deferred, named explicitly). `audit_logs` retention/archival policy once the table grows large enough to matter.

**Technical debt risk?** Low. This sprint closes existing debt (an audit trail nobody could read, a schema table nobody used) rather than creating new debt — the one deferred item (`core/logging.py` wiring) is named plainly, same practice as every prior sprint's honest scope boundary.

---

## Outstanding Decisions — must be resolved before implementation

1. **`audit_logs/models.py` special case**: since `AuditLog` already exists in `core/audit.py` and must not be duplicated, this module's `models.py` will contain a short docstring explaining the reuse and a `from app.core.audit import AuditLog` re-export (so `repository.py` and other files can still `from app.modules.audit_logs.models import AuditLog`, keeping the usual import shape) — rather than skipping `models.py` entirely. **Confirm this is the preferred approach**, versus importing `AuditLog` directly from `core.audit` in `repository.py` without any local `models.py` re-export.
2. **RBAC tier**: Super Admin only for both modules, as designed above — confirm, or should Admin also get read access to either?
3. **`system_logs` write access**: `POST /system-logs` restricted to Super Admin (manual incident recording) — confirm, or should this be more open (e.g. any Admin) since it's operational rather than behavioral data?
4. **Date range cap value**: needs a concrete number (e.g. 90 days, matching a reasonable audit-review window) rather than a placeholder — same category of decision as Sprint 8's file-size limits.
