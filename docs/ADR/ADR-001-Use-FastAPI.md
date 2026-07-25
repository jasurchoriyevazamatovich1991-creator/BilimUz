# ADR-001

## Title
Use FastAPI as the backend framework

## Status
Accepted

## Context
BilimUz needs a Python backend framework that supports millions of users, automatic API documentation (the platform will have dozens of consumers: React frontend, future Android/iOS apps, Telegram bot), strict input validation (education platforms handle sensitive data — grades, payments, personal info), and dependency injection clean enough to support Layered Architecture without a heavy add-on framework.

## Decision
Use **FastAPI** with **Pydantic v2** for validation and **Uvicorn** as the ASGI server.

## Consequences

**Positive:**
- Automatic OpenAPI/Swagger generation (`/docs`) — required by `docs/API/api_blueprint.md` and the API standards rule ("Document every endpoint") with near-zero extra work.
- Native `Depends()` system maps directly onto the project's Layered Architecture (`router → dependencies → service → repository`) without a third-party DI container.
- Async-ready from day one — even though current modules (`auth`, `subjects`) use sync SQLAlchemy `Session` for simplicity, migrating to `AsyncSession` later touches only `repository.py` per module (documented in each module's README).
- Pydantic v2 validation is fast (Rust core) and integrates with the strict input-validation requirement in `rules/05-security-checklist.md`.

**Negative:**
- Smaller enterprise-Java-style ecosystem (e.g. no built-in ORM migrations tool — Alembic is a separate dependency, see ADR-002 discussion).
- Async and sync code paths cannot be mixed carelessly; the team must consistently choose sync (current decision, see ADR-008) until load requires otherwise.

## Alternatives

| Option | Rejected because |
|---|---|
| Django + DRF | Heavier, opinionated ORM (harder to enforce our own Repository Pattern cleanly), slower for a pure API-first product |
| Flask | No native async, no built-in validation/OpenAPI — would require assembling FastAPI's features manually |
| Node.js (Express/NestJS) | Team and prompt system (`.cursor/prompts/`) are Python-first; NestJS was considered closest in philosophy but splits the stack across two languages unnecessarily |

## References
- `.cursor/prompts/01-architect.md`, `.cursor/prompts/03-backend.md`
- `backend/app/main.py`, `backend/app/auth/`, `backend/app/subjects/` (working implementation)
- https://fastapi.tiangolo.com
