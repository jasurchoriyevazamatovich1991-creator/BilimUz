# Audit Logs Module — BilimUz

Full design rationale: `docs/Sprint12_AuditLogs_SystemLogs_Architecture.md` (approved).

## Architecture

Same 8-layer pattern, **with one deliberate, documented exception**: `models.py` does not define a new SQLAlchemy class. `AuditLog` already exists in `app/core/audit.py` (Sprint 1), written to from **34 call sites across 20 modules** via `log_action()`. This module re-exports it (`from app.core.audit import AuditLog`) rather than redefining it — two ORM classes mapped to the same table would be a real, silent bug, not just a style issue. Per the approved decision: reuse the existing model, never duplicate it, never introduce a second audit implementation.

## Read-only, by design

This module has **no create/update/delete capability whatsoever** — no such methods exist in `AuditLogService`, no such routes exist in `router.py`. Every module that needs to record an audit event already does so via `core.audit.log_action()`, completely unchanged by this sprint. This module exists solely to make that data **visible** through the API for the first time — investigated before writing any code: the write side was already complete and correct; only the read side was missing.

## Business rules

- **`AuditLog` does not map `deleted_at`** (verified against `core/audit.py` before writing this module: only `TimestampMixin` is used, no soft-delete mixin) — the DB column exists but isn't mapped in code, so `AuditLogRepository` correctly does not filter by it (filtering by an unmapped attribute would raise `AttributeError`, not silently no-op).
- **Date range capped at 90 days** (approved decision) — a proactive guard against an unbounded query over a table with 34 active write call sites, growing indefinitely.
- **`metadata_` → `metadata` aliasing**: `AuditLog`'s Python attribute is necessarily named `metadata_` (SQLAlchemy reserves `metadata` on the declarative base itself), but the API response correctly exposes it as `metadata` — via Pydantic's `validation_alias`/`serialization_alias`, tested explicitly (`test_audit_log_schemas.py`). **Note**: this behavior could not be verified against a live `pydantic` install in this environment (no PyPI network access during development) — the pattern matches documented Pydantic v2 semantics and is covered by dedicated tests that will run in CI/a real environment.

## Database

Table: `audit_logs` (Module 24, `database/schema/schema_v2.sql`) — reused entirely via the existing `core/audit.py` model. **No schema change, no migration, `core/audit.py` itself is not modified.**

## API

```
GET /api/v1/audit-logs          — list/filter (user_id, action, entity_type, date range ≤90d)   Super Admin
GET /api/v1/audit-logs/{id}       — get one entry                                                   Super Admin
```

**Super Admin only, no Admin tier** (approved decision) — this is the most sensitive read surface in the platform, capable of revealing every user's actions across every module. Stricter than even `settings` (which protects infrastructure credentials; this protects behavioral data about every real person on the platform).

## Tests

Three files, 13 tests: `test_audit_log_validators.py` (5 — valid range, `None` dates allowed, start-after-end rejected, exact 90/91-day boundary), `test_audit_log_service.py` (5 — not-found, found, filter delegation, oversized-range rejection, filter pass-through), `test_audit_log_schemas.py` (3 — the `metadata_`/`metadata` aliasing guarantee, both directions, plus `None` handling).

## Future improvements
- Retention/archival policy once the table grows large enough to matter (no policy exists yet, flagged in the architecture doc as a Medium risk, not solved this sprint).
