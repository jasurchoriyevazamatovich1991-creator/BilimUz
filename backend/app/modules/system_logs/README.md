# System Logs Module — BilimUz

Full design rationale: `docs/Sprint12_AuditLogs_SystemLogs_Architecture.md` (approved).

## Architecture

Same 8-layer pattern, no exceptions this time — unlike `audit_logs` (built this same sprint), `system_logs` defines a genuinely **new** model, since nothing in the codebase has ever written to this table before.

## ⚠️ A table that's existed since Sprint 1 with zero producers — investigated, not assumed

Before writing any code, `core/logging.py` was read in full: it configures Python's standard `logging` module to write structured JSON to **stdout only**. It has never touched the `system_logs` table. This module gives the table real write **and** read capability for the first time — but does **not** wire `core/logging.py` to call it automatically. That integration is explicitly deferred (see Future Improvements) — Architecture Freeze: don't modify stable core infrastructure (`core/logging.py`, used by every request via `main.py` startup) without a specific, separately-approved reason.

## Business rules

- **`create_log()` uses the same calling convention as `core.audit.log_action()`** (plain method call, not an HTTP round-trip) — deliberately, so a future sprint can wire `core/logging.py`'s handler to call `SystemLogService.create_log()` directly on WARNING+ events, without this module needing to change.
- **`level` restricted to `info | warning | error | critical`** (schema comment, enforced at the validator layer).
- **No soft-delete convention** — `SystemLog` doesn't map `deleted_at` (schema column exists, not used in code), matching `AuditLog`'s exact precedent for consistency between the two "logs" modules: a log entry is an append-only record, not user-editable content the platform's usual soft-delete pattern was designed for.
- **Date range capped at 90 days** (approved decision, same value as `audit_logs`).

## Database

Table: `system_logs` (Module 25, `database/schema/schema_v2.sql`) — reused entirely, no schema change, no migration. `core/logging.py` is **not modified**.

## API

```
GET  /api/v1/system-logs             — list/filter (level, source, date range ≤90d)   Super Admin
GET  /api/v1/system-logs/{id}          — get one entry                                    Super Admin
POST /api/v1/system-logs                 — record a system-level event                      Super Admin
```

**Super Admin only, for both read and write** (approved decision) — system-level messages can contain internal details (stack traces, file paths) that shouldn't be broadly visible, consistent with the platform-wide rule that internal errors never reach a client response.

## Flow — record a system-level event

```
POST /system-logs {level, message, source?, context?}
  → SystemLogService.create_log(level, message, source, context)
      → validate level (schema-level, ALLOWED_LEVELS)
      → create SystemLog row
      → commit
      → return SystemLogOut
```

## Tests

Two files, 14 tests: `test_system_log_validators.py` (7 — all four allowed levels individually, invalid level rejected, empty/oversized message rejected, `None` source allowed, date-range boundary), `test_system_log_service.py` (7 — create with/without optional fields, not-found, found, oversized-range rejection, filter delegation, minimal-call defaults).

## Future improvements
- **`core/logging.py` → `SystemLogService.create_log()` wiring** — the single most valuable next step for this module: a custom logging `Handler` that calls `create_log()` on WARNING+ level events, giving the platform a queryable operational log instead of stdout-only visibility. Explicitly not done this sprint.
- Retention/archival policy, same open question as `audit_logs`.
