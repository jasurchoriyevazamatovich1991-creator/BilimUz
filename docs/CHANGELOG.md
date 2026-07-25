# Changelog

All notable changes to BilimUz are recorded here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/). Versions below track architecture/planning milestones, not deployed releases — nothing has shipped to production yet.

## [Unreleased]

### Added — Sprint 1: Foundation
- `app/db/` — split from the old combined `core/database.py` into `database.py` (engine), `base.py` (declarative Base), `session.py` (SessionLocal + `get_db()`) — single-responsibility per file
- `app/core/logging.py` — structured logging, wired into `main.py` startup
- `app/api/v1/health.py` — DB-connectivity-aware health check
- `app/api/v1/version.py` — app/environment/API version endpoint
- `backend/Dockerfile` — production image, non-root user, multi-stage-ready
- root `docker-compose.yml` — Postgres + Redis + backend, one-command local dev
- `backend/README.md` — full setup, structure, and testing guide
- Alembic initialized (`backend/alembic/`) — closes Senior Review Critical item #2. Baseline migration `0001_initial_schema.py` wraps the existing `schema_v2.sql` (54 tables); `schema_v2.sql` is now historical reference only, migrations are the live source of truth (`backend/alembic/README.md`)

### In Progress
- `roles` / `permissions` module backend (schema exists, no service/router yet — ADR-006)
- Migration not yet applied against a real Postgres instance (no DB available in this dev environment) — Senior Review Critical item #1 (test suite execution) remains open

---

## v0.4.0 — Test Engine (Planned, not started)

- Question Bank
- Test Engine
- Result System

Status: ❌ Not started. Depends on v0.3.0's `Tests`/`Topics` modules being complete first.

---

## v0.3.0 — Education Content (Partially complete)

### Added
- Subject Module — full CRUD, filter/search/sort/pagination, RBAC-protected writes (`backend/app/subjects/`)
- QA review of Subject Module: 3 bugs found and fixed (self-collision on rename, unrestricted status field, a test-suite false-positive) — see `backend/app/subjects/tests/TEST_PLAN.md`

### Planned, not started
- Topic Module
- Lesson Module

Status: 🟡 Subject done; Topic and Lesson not yet built.

---

## v0.2.0 — Authentication & Access Control (Partially complete)

### Added
- Authentication module: register, verify, login, refresh (with rotation), logout, logout-all-devices, session listing (`backend/app/auth/`)
- JWT access (15 min) + refresh (30 day) tokens, hashed refresh-token storage (ADR-004)
- Password policy: 12+ chars, mixed case, digit, special char, reuse prevention via `password_history`
- Redis-backed rate limiting on `/register`, `/login`, `/verify`
- Centralized audit logging (`core/audit.py`) for all auth events
- Security headers middleware (CSP, HSTS, X-Frame-Options, etc.)

### Planned, not started
- RBAC / Permissions module backend — `roles`, `permissions`, `role_permissions` tables exist in the schema (Module 4) but have no service/repository/router code yet (ADR-006)

Status: 🟡 Authentication and JWT complete; RBAC/Permissions schema-only.

---

## v0.1.0 — Architecture & Foundations

### Added
- Database Blueprint v2.0 — 54 tables, 25 modules, full audit trail (`created_at/updated_at/deleted_at/created_by/updated_by/status`), named constraints (`idx_/fk_/uq_`) (`database/schema/schema_v2.sql`)
- ER Diagram (`docs/Database/er_diagram.md`)
- Folder Architecture v1.0 — feature-based backend, Layered Architecture, full repo skeleton (`docs/00_Folder_Architecture.md`)
- API Blueprint — response envelope, endpoint contract per module (`docs/API/api_blueprint.md`)
- UI/UX Blueprint — page inventory, panel modules per role (`docs/UI-UX/`)
- AI Prompt System — 7 role prompts (`Architect`, `Database`, `Backend`, `Frontend`, `Security`, `QA`, `Reviewer`) persisted in `.cursor/prompts/`
- Enterprise Rules — 10 rule documents (`.cursor/rules/`)
- Project Context — 5 context documents reflecting live project state (`.cursor/context/`)
- First full Senior Review conducted against the built modules: **64/100 — CHANGES REQUIRED**

Status: ✅ Complete.

---

## Versioning note

Version numbers here track *planning/architecture milestones* as defined in `.cursor/context/03-roadmap.md`, not semantic versioning of a shipped API. Once `v1.0` (Authentication + Subjects + Tests + Results, all fully built and passing a Senior Review with `APPROVED` or `APPROVED WITH MINOR CHANGES`) is reached, this file switches to tracking real releases against `docs/API/api_blueprint.md`'s `/api/v1` contract.
