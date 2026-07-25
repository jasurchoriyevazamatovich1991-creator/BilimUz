# Database Schema

- **`schema_v2.sql`** — the original bootstrap schema (Chief Database Architect revision). 53 tables + `password_history` = 54, full audit trail, named constraints (`idx_`/`fk_`/`uq_`).
- **As of `backend/alembic/versions/0001_initial_schema.py`, this file is a historical reference, not the live source of truth.** Alembic migrations are now authoritative — see `backend/alembic/README.md`. Do not hand-edit `schema_v2.sql` to reflect new changes; write a new Alembic migration instead.
- Superseded: `schema_v1.sql` (kept in `docs/Database/` for historical reference only).

## Apply (bootstrap / fresh environment only)

```bash
createdb bilimuz
cd backend
alembic upgrade head
```

`alembic upgrade head` runs `0001_initial_schema.py`, which executes this exact `schema_v2.sql` content — so a fresh database ends up identical whether you ran the raw SQL file or Alembic. Prefer Alembic even for a brand-new database, so `alembic_version` is correctly initialized for all future migrations.

## Design decisions — see inline comments in schema_v2.sql for:
1. Circular FK resolution (`users` ↔ `roles`) via a bulk `DO $$ ... $$` loop for `created_by`/`updated_by`.
2. Why `role_permissions` is a full entity (id + audit) instead of a bare junction table.
3. Why event-log tables (`login_history`, `audit_logs`, `system_logs`) don't duplicate `created_by` on top of their own `user_id`.

