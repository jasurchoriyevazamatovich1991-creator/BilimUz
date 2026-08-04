"""
This module does NOT define its own model — `AuditLog` already exists
in `app/core/audit.py` (Sprint 1), written to from 34 call sites across
20 modules via `log_action()`. Per the approved architecture decision:
reuse the existing model, never duplicate it, never introduce a second
audit implementation.

This file re-exports `AuditLog` so `repository.py` (and anything else in
this module) can `from app.modules.audit_logs.models import AuditLog`,
keeping the same import shape every other module uses — without
redefining the SQLAlchemy class a second time (which would be a real
bug: two ORM classes mapped to the same table).

Note: `AuditLog` uses only `TimestampMixin` (no soft-delete mixin) —
verified against `core/audit.py` before writing this module. The
`audit_logs.deleted_at` DB column exists but is not mapped by this
model, so `repository.py` does not (and must not) filter by it.
"""
from app.core.audit import AuditLog

__all__ = ["AuditLog"]
