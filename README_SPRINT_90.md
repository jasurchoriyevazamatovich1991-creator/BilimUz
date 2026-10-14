# BilimUz — Sprint 90: Deployment Preparation and Production Readiness

## 1. Project overview

BilimUz is a FastAPI (backend) / React + TypeScript (frontend) e-learning and testing platform. It covers user/role management, subjects/grades/topics/lessons, test authoring and delivery, scoring, certificates, notifications, AI Center, and more (27 backend feature modules).

**Sprint 90 is deployment preparation, not application feature work.** Before this sprint, `nginx/`, `docker/`, and `docs/Deployment/` were all empty placeholders, and there was no production Docker Compose file, no frontend Dockerfile, and no backup/restore tooling — confirmed by direct inspection. This sprint adds all of that: a same-origin production architecture (nginx reverse proxy + two multi-stage Dockerfiles + a production Compose file), backup/restore scripts, and a full operational runbook. No application source code was changed.

> **Packaging note**: as with prior sprint archives, the repository's git history still ends at Sprint 67 (commit `449d316`) in the environment this archive was built in; Sprint 90, like every sprint since, exists only as uncommitted working-tree changes there. **This is unrelated to this repository's real GitHub history** — the repository owner committed and pushed Sprint 89 separately (commits `4771e0e`/`5452a54` on `main`) from their own machine before this archive was built. This archive is a cumulative project snapshot based on the current working tree, not Sprint-90-only code. No commit or push was performed to build this package.

## 2. Sprint 90 changes

**New deployment infrastructure:**
- `docker-compose.prod.yml` — production stack: Postgres and Redis have **no published host ports** (internal Docker network only); only the `web` (nginx) service is exposed, on port 80.
- `backend/Dockerfile.prod` — true multi-stage build (separate from the existing dev `backend/Dockerfile`): build tools (`gcc`, `libpq-dev`) never reach the final image; runs as a non-root user; includes a `HEALTHCHECK` against `/api/v1/health`; runs `uvicorn` with `--proxy-headers --forwarded-allow-ips='*'`.
- `frontend/Dockerfile` — new (none existed before). Multi-stage: builds the Vite app (`node:20-alpine`), then serves it via `nginx:1.27-alpine`, which also reverse-proxies `/api/v1/`, `/docs`, and `/api/v1/openapi.json` to the backend on the same origin.
- `nginx/nginx.conf` — new (the directory was empty before). Serves the built SPA with a client-side-routing fallback, proxies the API, sets `X-Forwarded-For`/`X-Real-IP`/`X-Forwarded-Proto`. Ships with HTTP only; includes a clearly commented-out HTTPS server block with placeholder certificate paths — **not** a working TLS setup, by design (no certificate was fabricated).
- `backend/.env.production.example`, `docker-compose.prod.env.example`, `frontend/.env.production.example` — production configuration templates using the exact variable names from `backend/app/core/config.py`'s `Settings` class; placeholders only, no real secrets.
- `backend/.dockerignore`, `frontend/.dockerignore` — new (none existed before).
- `scripts/backup_db.sh`, `scripts/restore_db.sh` — new (no backup automation existed before). `pg_dump`/restore via `docker compose exec`, no database port needs to be published for either to work.
- `docs/Deployment/PRODUCTION.md` — new operational runbook: architecture, environment setup, HTTPS/cookie/CSRF/CORS notes specific to this app's Sprint 86 cookie implementation, deploy commands, backup/restore/recovery procedure, health checks, troubleshooting, and an explicit "what was actually validated vs. what requires a real server" section.

**A real, pre-existing gap this sprint found and fixed while building the proxy config**: `app/core/middleware/rate_limit.py` keys its IP-based rate limiter on `request.client.host`, which — behind an unconfigured reverse proxy — would see every request as coming from the proxy's own container IP, collapsing all real visitors into one shared rate-limit bucket. Fixed via `--proxy-headers --forwarded-allow-ips='*'` on the backend (safe specifically because the backend has no published port) plus the corresponding forwarded headers in `nginx.conf`.

**Small, accurate documentation updates** (no application code changed): `docs/ADR/ADR-007-Use-Docker.md`'s status section updated to reflect that the production side (previously "a placeholder") is now implemented; root `README.md` §11 updated to stop claiming `nginx/`/`scripts/` are empty; `docs/RELEASE_PACKAGING.md` updated with the new `.env.production` exclusion rule and the new files now included in a release archive; `.gitignore` extended to cover `backend/.env.production` and `frontend/.env.production`.

## 3. Requirements

- **Docker Engine with the Compose v2 plugin** (`docker compose version`) — new requirement for this sprint's production path; local dev (section 4/5 of root `README.md`) still works without Docker.
- Everything the application itself already required (Python 3.13, Node 20+, PostgreSQL 16, Redis 7) — unchanged, see `backend/requirements.txt` / `frontend/package.json`.

## 4. Deployment setup

```bash
cd BilimUz   # repository root
cp docker-compose.prod.env.example .env
cp backend/.env.production.example backend/.env.production
# edit both with real values — see docs/Deployment/PRODUCTION.md section 3

docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d postgres redis
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
docker compose -f docker-compose.prod.yml up -d
```

Full procedure, including HTTPS setup options, backups, and troubleshooting: [`docs/Deployment/PRODUCTION.md`](docs/Deployment/PRODUCTION.md).

## 5. Backend and frontend setup (local development, unchanged)

See the root [`README.md`](README.md) sections 6–7 — this sprint did not change local development setup at all.

## 6. Configuration

Production configuration uses the exact variable names in `backend/app/core/config.py`'s `Settings` class — see `backend/.env.production.example` and `docker-compose.prod.env.example` for the full, documented list with placeholders only. Never commit the filled-in files (both are `.gitignore`d). No secret values appear anywhere in this document, the release notes, or the final report that accompanied this sprint's work.

## 7. Testing commands and results

Run in the environment this archive was prepared in:

```bash
cd backend && python -m pytest app/core/tests/ -q
```
**Result: 58 passed, 1 skipped** (ENVIRONMENT/secret-safety validation — directly relevant to this sprint's production config).

```bash
cd backend && python -m pytest app/ scripts/ -q
```
**Result: 687 passed, 1 skipped** (full backend unit/mock suite — confirms no application code regressed).

```bash
cd frontend && npm run test -- --run
```
**Result: 473 passed.**

## 8. Build and lint commands and results

```bash
cd frontend && npx tsc -b --noEmit
```
**Result: 0 errors.**

```bash
cd frontend && npm run lint
```
**Result: 0 errors, 5 pre-existing warnings**, all in files unrelated to this sprint.

```bash
cd frontend && VITE_API_BASE_URL=/api/v1 npm run build
```
**Result: succeeded.** Manually confirmed the built bundle contains the literal `"/api/v1"` and zero occurrences of `localhost:8000` — the same-origin relative API base URL this deployment's architecture depends on is actually what gets baked into the production bundle.

```bash
docker compose -f docker-compose.prod.yml config
```
**Result: succeeded** (exit 0) — confirms the Compose file is syntactically valid and, on manual review of the resolved output, that Postgres/Redis have no published ports while only `web` does.

## 9. Known limitations

- **Not deployed to or verified against a real server.** Docker CLI is present in the environment this was built in, but the Docker daemon was not running (`docker info` fails to reach `/var/run/docker.sock`) — actual image builds (`docker compose build`) and running the stack (`docker compose up`) were **not** executed. `nginx -t` was not run (no nginx binary available) — the config was reviewed manually instead.
- **HTTPS is not configured out of the box.** `nginx/nginx.conf` serves plain HTTP; a commented, placeholder-only HTTPS server block is provided as a template, not a working setup. The backend's own cookie code already enforces `Secure=True` outside `ENVIRONMENT=development`, so this deployment will not function correctly for real users until real HTTPS is configured — see `docs/Deployment/PRODUCTION.md` section 5.
- No automated rollback, blue/green deploy, monitoring/alerting stack, or backup retention/pruning — all documented as explicit, unaddressed limitations rather than silently left out.
- `FILE_ENCRYPTION_KEY` rotation has no migration path (pre-existing limitation of the encryption-at-rest design, not something this sprint solves).
- `docker/` remains an empty placeholder — nothing needed to go there; all production content lives in `nginx/`, the two Dockerfiles, and `docker-compose.prod.yml`.

## 10. Archive contents, exclusions, and extraction

Same conventions as the Sprint 89 archive (`docs/RELEASE_PACKAGING.md`): a cumulative project snapshot, excluding `.git/`, real `.env`/`.env.production` files, `venv/`/`node_modules/`/`dist/`, caches, local uploads, database backups, logs, and any nested `*.zip`.

```bash
unzip BilimUz-Sprint-90.zip
cd BilimUz
```
Then follow section 4 (deployment) or the root `README.md` sections 6–7 (local development).

## 11. Repository and license

GitHub repository: https://github.com/jasurchoriyevazamatovich1991-creator/BilimUz

**License**: the repository's root `LICENSE` file exists but is **empty** — no license has been specified for this project. This document does not assume or invent one.
