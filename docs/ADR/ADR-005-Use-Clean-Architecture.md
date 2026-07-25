# ADR-005

## Title
Use Clean/Layered Architecture with a feature-based Modular Monolith

## Status
Accepted — implemented consistently in `backend/app/auth/` and `backend/app/subjects/`

## Context
BilimUz must support 25 backend modules (Authentication through Settings) that will be built over years by potentially different teams, while remaining a single deployable unit at v1.0 (a full microservices split is explicitly out of scope until traffic proves it necessary — see `docs/Roadmap`). The risk being designed against: business logic leaking into routers, SQL queries scattered across services, and modules becoming tangled enough that no single module could later be extracted into its own service without a rewrite.

## Decision
Every module follows the same 8-file layered pattern: `router.py → dependencies.py/validators.py → service.py → repository.py → models.py`, plus `schemas.py`, `exceptions.py`, `constants.py`, `tests/`, and `README.md`. Cross-cutting concerns (JWT, DB session, audit logging, rate limiting) live in `core/`, imported by modules but never the reverse.

## Consequences

**Positive:**
- `service.py` never imports `fastapi` (verified during Senior Review) — business logic is framework-agnostic and testable without spinning up an HTTP server, and reusable from a future CLI or Telegram bot with zero changes.
- A module can be extracted into its own microservice later by moving its folder + its section of `schema_v2.sql` — because it never reaches into another module's `repository.py` directly.
- New modules are fast to scaffold correctly because the pattern is identical every time (`subjects` took a fraction of the time `auth` did, precisely because the shape was already proven).

**Negative:**
- More files per module (10+) than a simpler "one file per resource" approach — a deliberate trade-off; `rules/01-coding-standards.md`'s 300-line file / 40-line function limits only stay achievable *because* of this split.
- Not strict DDD (no separate domain-entity layer distinct from the SQLAlchemy model) — documented explicitly in the Senior Review as a named, accepted deviation rather than an oversight.

## Alternatives

| Option | Rejected because |
|---|---|
| MVC (routes + one big `models.py` per app) | Common in smaller Django/Rails apps, but doesn't scale past a handful of modules without business logic ending up in views/routes — exactly what the Backend Engineer prompt forbids |
| Full microservices from day one | Massively increases operational complexity (service discovery, distributed transactions for e.g. "create result → generate certificate") before the platform has a single real user; the Modular Monolith gets 80% of the benefit at a fraction of the cost |
| Full DDD with separate domain/infrastructure/application layers | More rigor than justified at this stage; the team can migrate toward it per-module later if a module's business logic genuinely outgrows the current pattern |

## References
- `.cursor/prompts/01-architect.md`, `.cursor/prompts/03-backend.md`
- `docs/00_Folder_Architecture.md`
- `backend/app/auth/README.md`, `backend/app/subjects/README.md`
