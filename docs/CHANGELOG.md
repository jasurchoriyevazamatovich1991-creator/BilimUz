# Changelog

All notable changes to BilimUz are recorded here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/). Versions below track architecture/planning milestones, not deployed releases — nothing has shipped to production yet.

## [Unreleased]

### Sprint 7 — Results, Certificates, Analytics
- `app/modules/results/` — Result creation (idempotent on attempt_id), Statistics (running-average upsert), Ranking calculation ENGINE ONLY (no public leaderboard read endpoint — approved scope limit). Tie-break: higher score → shorter duration → earlier completion. 13 test cases.
- `app/modules/certificates/` — Certificate issuance idempotent per (user_id, test_id), public verification by code, templates. `pdf_url` always null — PDF export explicitly out of scope this sprint, not a placeholder. 12 test cases.
- `app/modules/analytics/` — fully independent module (no write dependency from `results`, per approved architecture): computes `daily_statistics`/`monthly_statistics` via explicit Admin-triggered recompute, reading `results` + `attempts` answers read-only. Delete-and-rebuild strategy, N+1-safe subject caching. 11 test cases.
- Full architecture design document, 2 revisions: `docs/Sprint7_Results_Certificates_Analytics_Architecture.md` — Revision 1 (initial design) → Revision 2 (4 approved decisions: Analytics independence, certificate idempotency key, PDF deferral, ranking tie-break rule)
- One bug caught and fixed during development (not shipped): a placeholder `_subject_for()` in `analytics/service.py` that always returned `None` — replaced with a real, cached, N+1-safe subject lookup before the module was considered complete
- No new migrations — all 10 tables already existed in the baseline (`0001_initial_schema.py`)
- Total Sprint 7 tests: 36

### Sprint 6 — Test Engine (Tests, Questions, Attempts)
- `app/modules/tests/` — Test definitions: CRUD, publish-readiness state machine (draft→published→archived), 10 test cases
- `app/modules/questions/` — Question + QuestionOption + QuestionMedia (3 entities, 1 module, `permissions`-pattern grouping): CRUD, answer-key validation (single/multiple/true-false rules), 15 test cases. One bug found and fixed during development: a silently-swallowed `try/except: pass` in `add_option()` was replaced with a real, always-enforceable single-correct-answer check.
- `app/modules/attempts/` — the stateful test-taking engine: start/resume/answer/submit/result, server-authoritative timer, persisted question randomization, lazy auto-finish (no background worker needed), 22 test cases including an explicit "unanswered questions score zero" test
- Alembic migration `0002_add_attempt_expiry_and_question_order.py` — adds `expires_at` and `question_order` to `test_attempts` (architecture decision: persist, don't recompute, for full attempt reproducibility)
- One additive method to the existing `questions` module (`QuestionRepository.list_all_for_test()`) — required by `attempts` for unpaginated question snapshotting; no existing behavior changed
- Full architecture design document: `docs/Sprint6_TestEngine_Architecture.md` (written and approved before any code)
- Removed 7 more stray empty scaffold folders (`app/permissions/`, `app/tests/`, `app/questions/`, `app/attempts/`, `app/options/`, `app/database/`, `app/middleware/` — the last two superseded since Sprint 1's `app/db/`/`app/core/middleware/` split, only now actually deleted)
- Total Sprint 6 tests: 47

### Sprint 5 — Education Core (Grades, Topics, Lessons)
- `app/modules/grades/` — full CRUD module: pagination, search, sort, filter, soft delete, UUID, 7 test cases
- `app/modules/topics/` — full CRUD module, cross-module referential validation against `subjects` and `grades` (422 on invalid references instead of a raw DB error), 8 test cases
- `app/modules/lessons/` — full CRUD module, cross-module referential validation against `topics`, enforces "at least one content type" (video/pdf/content) on both create (schema-level) and update (service-level merge check), 8 test cases
- All three follow the exact `auth`/`users` architectural pattern: `models, schemas, repository, service, router, dependencies, validators, exceptions, constants, tests/, README.md`
- Full Swagger documentation (`summary` + `description` on every endpoint and query parameter)
- Removed 3 stray empty scaffold folders (`app/grades/`, `app/topics/`, `app/lessons/` at the old pre-`app/modules/` location) — repository is cleaner than before Sprint 5, per the sprint's explicit goal

### Sprint 4 — Auth Cutover
- Merged the isolated Sprint 3 Argon2/JWT track into the single production `auth` module — see `docs/ADR/ADR-009-Auth-Cutover.md`
- `PasswordService` (Argon2) and `JWTService` (typed payloads, `nbf` claim) promoted to shared infrastructure: `app/core/security/`
- Password policy resolved to **12 characters** (final)
- Removed: `app/modules/auth/{security,jwt,registration,login,refresh,me}/` and their `-v2` endpoints — no client-facing path changes, `/auth/register` `/auth/login` `/auth/refresh` `/auth/me` etc. now run the upgraded implementation
- Fixed permanently (carried over from Sprint 3): `get_current_user()` now catches `pydantic.ValidationError` in addition to `jwt.PyJWTError` when decoding tokens, closing an unhandled-500 risk

### Sprint 3 — Isolated Argon2/JWT authentication track (superseded by Sprint 4 cutover above)
- Built `PasswordService`, `JWTService`, and Register/Login/Refresh/Me APIs as a self-contained parallel implementation, per explicit "do not modify existing endpoints" scope on each step
- 36 unit tests written across the 6 isolated modules
- Found and fixed a real compatibility gap (old-system tokens missing the `nbf` claim causing an unhandled `pydantic.ValidationError`) — the fix was carried forward into the Sprint 4 cutover

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
