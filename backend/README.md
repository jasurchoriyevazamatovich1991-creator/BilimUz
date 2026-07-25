# BilimUz Backend

FastAPI backend for the BilimUz education platform. See `docs/00_Folder_Architecture.md` for the full architectural rationale and `docs/ADR/` for why each major technology was chosen.

## Stack

Python 3.13, FastAPI, PostgreSQL, SQLAlchemy 2.x, Alembic, Pydantic v2, Redis, JWT.

## Project structure

```
app/
├── main.py              # FastAPI app instance, middleware, startup logging
├── core/
│   ├── config.py          # Settings (env-driven, single source of truth)
│   ├── security.py         # Password hashing, JWT create/verify
│   ├── logging.py           # Structured logging setup
│   ├── exceptions.py         # AppException hierarchy + global handler
│   ├── schemas.py              # Shared {success, message, data, errors} envelope
│   ├── mixins.py                 # UUID PK / timestamp / audit / status mixins
│   ├── audit.py                    # Centralized audit_logs writer
│   ├── redis_client.py               # Single Redis client instance
│   └── middleware/                     # Rate limiting, security headers
├── db/
│   ├── database.py          # SQLAlchemy engine (connection pooling)
│   ├── base.py                # Declarative Base — every model.py imports from here
│   └── session.py               # SessionLocal + get_db() FastAPI dependency
├── api/
│   ├── router.py             # Aggregates every module + v1 router under /api/v1
│   └── v1/
│       ├── health.py           # GET /api/v1/health — checks DB connectivity
│       └── version.py            # GET /api/v1/version — app/env/API version info
├── auth/                    # Feature module (see auth/README.md)
├── subjects/                # Feature module (see subjects/README.md)
└── {other 23 modules}/      # Scaffolded, not yet implemented — .cursor/context/05-system-modules.md
```

**Two kinds of code live in `app/`:** foundation (`core/`, `db/`, `api/v1/`) that every module depends on, and feature modules (`auth/`, `subjects/`, ...) that depend on the foundation but never on each other directly. See `docs/ADR/ADR-005-Use-Clean-Architecture.md`.

## Local development

### Option A — Docker (recommended)

```bash
cp backend/.env.example backend/.env   # fill in real values, especially JWT_SECRET_KEY
docker-compose up --build
```

This starts Postgres, Redis, and the backend (with `--reload`) together. API available at `http://localhost:8000`, interactive docs at `http://localhost:8000/docs`.

### Option B — Local Python

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # point DATABASE_URL at a Postgres you're running yourself
alembic upgrade head
uvicorn app.main:app --reload
```

## Database migrations

See `backend/alembic/README.md`. Short version: `alembic upgrade head` to apply, `alembic revision --autogenerate -m "..."` to create a new one — but only for modules that already have a `models.py` (check `alembic/env.py`'s import list first).

## Endpoints available today

```
GET  /api/v1/health     — service + database connectivity check
GET  /api/v1/version    — app name, version, environment
GET  /docs               — Swagger UI (auto-generated)
POST /api/v1/auth/*        — see auth/README.md
GET  /api/v1/subjects/*      — see subjects/README.md
```

## Testing

```bash
cd backend
pip install -r requirements.txt
pytest
```

**Honest status** (see `docs/CHANGELOG.md`): tests are written for `auth` and `subjects` but have never been executed against a real environment — this dev environment has no network access to install dependencies or run Postgres. Run them for real before trusting them as verification, not just documentation.

## What's NOT here yet

Per the current sprint's scope, business modules beyond `auth`/`subjects` (Login flows beyond basic JWT, full RBAC/Permissions, Tests, AI, Payments) are intentionally not implemented — see `.cursor/context/05-system-modules.md` for the honest per-module status.

## Future improvements

- Root-level unversioned `/health` (in addition to `/api/v1/health`) for load balancers/Kubernetes probes that shouldn't need to know the API version.
- Structured logging via `structlog` instead of the stdlib-based formatter in `core/logging.py`, if log volume/querying needs grow.
- Async SQLAlchemy (`AsyncSession`) if request concurrency needs outgrow the current sync `Session` model — by design, only `repository.py` files per module would need to change.
