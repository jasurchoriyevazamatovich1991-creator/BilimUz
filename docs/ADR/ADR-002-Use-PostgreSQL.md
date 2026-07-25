# ADR-002

## Title
Use PostgreSQL as the primary database

## Status
Accepted

## Context
BilimUz's data model (54 tables, `database/schema/schema_v2.sql`) requires strict relational integrity — a test result must always point to a real user, test, and attempt; a certificate must always point to a real result. It also needs JSONB columns for semi-structured data (`ai_settings.criteria` for badges, `test_attempts.anti_cheat_flags`, `study_plans.plan`), full audit trails on every table, and the ability to scale to millions of rows in `results`, `test_attempts`, and `answers` without redesign.

## Decision
Use **PostgreSQL** (not MySQL, not a NoSQL document store) as the single system of record, accessed through **SQLAlchemy 2.x** with **Alembic** for migrations.

## Consequences

**Positive:**
- Native `UUID`, `JSONB`, `ENUM`, and `INET` types map directly onto the database rules (`rules/06-database-rules.md`) without workarounds.
- Strong FK/constraint enforcement makes "never create orphan records" (Database Architect prompt) enforceable at the DB level, not just in application code.
- The circular `users` ↔ `roles` foreign key was solvable cleanly with a PL/pgSQL `DO $$` block (`schema_v2.sql`) — a capability not available in simpler databases.
- Mature ecosystem for the millions-of-users scale target: read replicas, partitioning (e.g. `test_attempts` by date) are available later without a database migration.

**Negative:**
- Requires an explicit migration discipline (Alembic) to avoid manual schema drift — currently a **known gap**: `backend/alembic/` is not yet initialized (see Senior Review, `docs/Roadmap` follow-up).
- Vertical scaling has a ceiling eventually reached by any single-writer relational database; the architecture is intentionally a "Modular Monolith" (ADR-005) so individual modules could later be split onto separate databases if one becomes a bottleneck (e.g. `analytics`).

## Alternatives

| Option | Rejected because |
|---|---|
| MySQL | Weaker JSONB/array support, less expressive constraint system for the audit-heavy schema |
| MongoDB | Education platform data is inherently relational (users → attempts → results → certificates); a document model would force manual referential integrity that PostgreSQL gives for free |
| SQLite | No concurrent-write scalability; explicitly rejected in the Database Architect prompt ("Never use SQLite" pattern implied by "PostgreSQL (not SQLite)") |

## References
- `.cursor/prompts/02-database.md`
- `database/schema/schema_v2.sql`, `database/schema/README.md`
- `docs/Database/database_blueprint.md`, `docs/Database/er_diagram.md`
