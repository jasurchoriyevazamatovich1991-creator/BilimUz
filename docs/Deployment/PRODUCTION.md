# BilimUz — Production Deployment (Sprint 90)

This document is the operational runbook for deploying BilimUz to a single
server. It was written for `docs/Deployment/`, which existed only as an
empty placeholder (`.gitkeep`) before this sprint — this is the first real
content there. It covers everything the actual deployment files in this
repository (`docker-compose.prod.yml`, `backend/Dockerfile.prod`,
`frontend/Dockerfile`, `nginx/nginx.conf`) implement, and nothing beyond
that — see "Known limitations" at the end for what this deliberately does
not cover.

**Scope and honesty note**: this document describes deployment
*preparation* — the configuration has been written and statically
validated (see "What was actually validated" below), but it has **not**
been deployed to or verified against a real server. Commands marked
"verified locally" were actually run in this environment; everything
else is marked "requires a real server" and has not been executed.

## 1. Architecture

Same-origin, single-server, four containers:

```
                 ┌─────────────────────────────┐
  Internet ───▶  │  web (nginx)  — port 80/443  │
                 │  - serves built React SPA    │
                 │  - proxies /api/v1/ ─────────┼──▶ backend:8000 (internal only)
                 │  - proxies /docs              │        │
                 └─────────────────────────────┘        │
                                                           ▼
                                              ┌─────────────────────┐
                                              │  postgres (internal) │
                                              │  redis (internal)    │
                                              └─────────────────────┘
```

**Why same-origin, not split frontend/API hostnames**: the backend's
refresh-token and CSRF cookies (`backend/app/core/security/cookies.py`,
Sprint 86) default to `SameSite=Lax` with no cookie `Domain` set — correct
and simplest when frontend and backend are served from the exact same
hostname, which is what `nginx/nginx.conf` does (it serves the SPA's
static files AND proxies `/api/v1/` to the backend on the same origin).
A split-hostname deployment is possible but requires `SameSite=None` +
HTTPS + `REFRESH_TOKEN_COOKIE_DOMAIN` and is out of scope here — see that
file's own Sprint 86 section if you need it.

Only the `web` service is published to the host/public internet.
`postgres` and `redis` have **no** `ports:` mapping in
`docker-compose.prod.yml` — reachable only on the internal Docker
network, by `backend` and (for postgres) the backup scripts. This was a
deliberate change from the existing `docker-compose.yml` (local-dev
stack), which does publish both to the host for local tool access
(`psql`, a GUI client) — that is correct for dev and wrong for
production, so the production file does not reuse it.

## 2. Server prerequisites

- A Linux server (any distribution with a working Docker install) with
  **Docker Engine and the Compose plugin** (`docker compose version`
  should report v2.x or newer).
- A domain name pointed at the server's public IP, if you want a real
  hostname (not required to run the stack, required for real HTTPS — see
  section 5).
- Enough disk for: the Postgres data volume (grows with your data),
  Docker images (~1–2 GB total for all four), and backup output
  (`database/backups/`, grows with each `pg_dump`; see section 7 on
  retention).
- Outbound HTTPS access from the server, if `AI_PROVIDER=anthropic` is
  enabled (the backend calls `api.anthropic.com` directly — Sprint 88).

## 3. Environment setup

Two separate files need real values before first deploy — neither is
committed (both are `.gitignore`d; only their `*.example` counterparts
are tracked):

```bash
cd BilimUz   # repository root

# 1. Variables docker-compose.prod.yml itself interpolates
cp docker-compose.prod.env.example .env

# 2. Variables the backend PROCESS reads
cp backend/.env.production.example backend/.env.production
```

Edit both. `docker-compose.prod.env.example` and
`backend/.env.production.example` each explain, inline, what every
variable is and which ones are **required** to have a real (non-
placeholder) value before the backend will even start — see section 4
for why that's enforced automatically, not just a suggestion.

**Generate real secrets** (never reuse the examples below as actual
values — these are commands, not values):
```bash
# JWT_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(64))"

# FILE_ENCRYPTION_KEY (must be a valid Fernet key specifically)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# POSTGRES_PASSWORD — any strong random string; must be identical in
# both files (see docker-compose.prod.env.example's own note on this)
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

This report does not display or claim any specific secret values — see
the `*.example` files for the exact variable names and their meaning,
and `backend/app/core/config.py` for the authoritative source (every
name in the example files was copied from there, none invented).

## 4. Fail-closed secret validation (already implemented, not new)

`backend/app/core/config.py::validate_production_secrets()`, called from
`app/main.py`'s startup handler, **already** refuses to start the
backend when `ENVIRONMENT` is `production` or `staging` and
`JWT_SECRET_KEY` / `FILE_ENCRYPTION_KEY` are still at their public,
repository-visible placeholder values (and `R2_*` / `AI_API_KEY` too,
but only when `STORAGE_BACKEND=r2` / `AI_PROVIDER=anthropic`
respectively are also set). This sprint did not add or change that
logic — it was already correct (Sprint 73, extended Sprint 81/88) — this
document just explains it so an operator understands *why* a container
that looks like it started will immediately exit if a secret was left
unset.

Verified in this sprint: `python -m pytest app/core/tests/ -q` → **58
passed, 1 skipped** (installs this project's `requirements.txt` into
this environment to actually run them — see section 9).

## 5. HTTPS, cookies, CSRF, CORS

- **HTTPS is not enabled by default.** `nginx/nginx.conf` serves plain
  HTTP on port 80 and explicitly does **not** include a fake or
  self-signed certificate (see that file's own header comment for the
  two real options — a separate TLS-terminating proxy you already run,
  or terminating TLS in the `web` container with a real certificate,
  e.g. via Let's Encrypt/certbot). Do not expose this to real users
  carrying real credentials over plain HTTP in production — see the
  enforcement note next.
- **Enforcement, not just a recommendation**: `cookies.py::_is_secure()`
  sets `Secure=True` on the refresh-token and CSRF cookies whenever
  `ENVIRONMENT != "development"`. Once you set
  `ENVIRONMENT=production`/`staging` in `backend/.env.production`,
  browsers will **refuse to send those cookies back over plain HTTP** —
  login will appear to work but every subsequent authenticated request
  will silently fail to refresh. This is correct, existing, fail-closed
  behavior; the practical implication is that you must configure real
  HTTPS (section above) before this deployment is actually usable in
  production, not just reachable.
- **CSRF**: `X-CSRF-Token` is already in `app/main.py`'s CORS
  `allow_headers` list; the frontend already reads the `csrf_token`
  cookie and sends that header on `/auth/refresh` and `/auth/logout`
  (pre-existing Sprint 86 behavior, not changed here).
- **CORS**: `ALLOWED_ORIGINS` in `backend/.env.production.example`
  defaults to a placeholder (`https://your-real-domain.example`) —
  replace with your real domain. In the same-origin architecture this
  document describes, the frontend never makes a cross-origin request to
  the backend at all (it's proxied through the same nginx origin), so
  `ALLOWED_ORIGINS` mainly matters for any OTHER client calling the API
  directly (e.g. a future mobile app).
- **Forwarded headers / client IP**: `app/core/middleware/
  rate_limit.py` keys its fixed-window rate limiter on
  `request.client.host`. Behind nginx, that would otherwise always be
  nginx's own container IP (collapsing every real visitor into one
  shared rate-limit bucket) unless uvicorn is told to trust forwarded
  headers from its direct connector. `backend/Dockerfile.prod`'s `CMD`
  already includes `--proxy-headers --forwarded-allow-ips='*'`, and
  `nginx/nginx.conf` already sets `X-Forwarded-For`/`X-Real-IP`/
  `X-Forwarded-Proto` on its proxied requests — this is safe specifically
  because `backend` has no published port and is reachable only from
  `web` on the internal Docker network (verified via `docker compose
  config`, see section 9). **This was an issue this sprint identified
  and fixed while writing the proxy config** — it did not exist before
  because there was no reverse proxy before Sprint 90.
- **Cross-origin/cross-subdomain auth is NOT claimed to work** — this
  deployment is same-origin by design and that combination has not been
  tested.
- **Streaming/WebSockets**: not used anywhere in this application
  (confirmed — the AI Center's `send message` endpoint returns one
  complete response per request, per `README_SPRINT_88.md`); no
  WebSocket proxy configuration was added, because none is needed.

## 6. Build and deploy commands

All run from the repository root.

**First deployment:**
```bash
cp docker-compose.prod.env.example .env
cp backend/.env.production.example backend/.env.production
# edit both files with real values — see section 3

docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d postgres redis
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
```

**Updating to a new version** (after `git pull`/redeploying new code):
```bash
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head   # section 7: back up first
docker compose -f docker-compose.prod.yml up -d
```

Migrations are **never** run automatically on container start — this is
a deliberate choice (see `docker-compose.prod.yml`'s own comment on the
`backend` service): auto-migrating on boot hides a failed migration
behind a restart loop and is unsafe to combine with any future
multi-replica setup. Run `alembic upgrade head` explicitly, as its own
visible step, every time.

**First Super Admin user** (same script as local dev, now via `docker
compose exec`):
```bash
docker compose -f docker-compose.prod.yml exec backend \
    env SUPERADMIN_EMAIL=admin@your-real-domain.example SUPERADMIN_PASSWORD=YOUR_STRONG_PASSWORD \
    python scripts/seed_admin.py
```

## 7. Database persistence, backups, and recovery

- **Persistence**: `postgres`'s data directory is a named Docker volume
  (`bilimuz_postgres_data`, declared in `docker-compose.prod.yml`) — it
  survives `docker compose down` and container recreation. It is only
  lost if the volume itself is explicitly removed (`docker compose down
  -v`, or `docker volume rm`) — never do this on a production server
  without a fresh backup already in hand.
- **Backups**: `scripts/backup_db.sh` (new this sprint — no backup
  automation existed before) runs `pg_dump` inside the running
  `postgres` container (no published DB port needed) and writes a
  gzip-compressed SQL dump to `database/backups/`. Run it manually, or
  schedule it:
  ```bash
  # crontab -e, as whichever user has docker compose access:
  0 3 * * * cd /path/to/BilimUz && ./scripts/backup_db.sh >> /var/log/bilimuz-backup.log 2>&1
  ```
  **This cron line is a recommendation to add yourself** — it is not
  installed or scheduled by anything in this repository; no cron job
  was created as part of this sprint.
- **Backup before migration**: always run `./scripts/backup_db.sh`
  before `alembic upgrade head` on an existing production database — if
  a migration fails partway or does something unexpected, this is your
  rollback path (Alembic migrations are not all automatically
  reversible — check the specific migration in `backend/alembic/
  versions/` before assuming `alembic downgrade` is safe).
- **Restore**: `scripts/restore_db.sh <backup-file> [--yes]` (new this
  sprint) — destructive, drops and recreates the database before
  loading the dump; requires typed `yes` confirmation unless `--yes` is
  passed. See that script's own header comment for the full behavior.
- **Verification after restore**: the script prints row counts for
  `users`, `tests`, `test_attempts` as a basic sanity check (table names
  confirmed against `backend/app/modules/*/models.py`, not guessed), and
  tells you to run `alembic current` to confirm the restored schema
  matches what the current backend code expects.
- **Safe recovery if an upgrade fails**: stop the `backend` container
  (`docker compose -f docker-compose.prod.yml stop backend`) before
  anyone can hit a half-migrated schema, restore the pre-migration
  backup with `restore_db.sh`, then redeploy the previous working image
  (`docker compose -f docker-compose.prod.yml up -d backend` after
  checking out the previous code revision and rebuilding) — there is no
  automated rollback in this repository; this is a manual procedure.

## 8. Health checks, logs, restart, troubleshooting

**Health checks:**
```bash
curl http://localhost/healthz             # nginx itself (no backend/DB involved)
curl http://localhost/api/v1/health       # proxied to the backend; checks DB connectivity
docker compose -f docker-compose.prod.yml ps   # shows each container's Docker-level health status
```
Note: `GET /api/v1/health` (`backend/app/api/v1/health.py`, pre-existing,
not changed this sprint) always returns HTTP 200, even when the database
is unreachable — it reports `{"status": "degraded", "database":
"unreachable"}` in the body in that case. A monitoring tool checking
only the HTTP status code will not catch a degraded database; check the
JSON body if you need that distinction.

**Logs:**
```bash
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f web
docker compose -f docker-compose.prod.yml logs --since 1h postgres
```

**Restart:**
```bash
docker compose -f docker-compose.prod.yml restart backend   # one service
docker compose -f docker-compose.prod.yml up -d              # recreate any changed service
```

**Secret rotation** (e.g. `JWT_SECRET_KEY`): edit
`backend/.env.production`, then `docker compose -f
docker-compose.prod.yml up -d backend` to recreate just that container
with the new value. Rotating `JWT_SECRET_KEY` invalidates every
existing access/refresh token — all users are signed out. Rotating
`FILE_ENCRYPTION_KEY` is **not** a safe drop-in rotation — every row
already encrypted with the old key becomes unreadable with the new one;
this requires a decrypt-with-old/re-encrypt-with-new migration that does
not exist in this codebase (noted as a limitation below, not solved
here).

**Troubleshooting:**
| Symptom | Likely cause |
|---|---|
| `backend` container exits immediately after start | A `JWT_SECRET_KEY`/`FILE_ENCRYPTION_KEY`/(R2\|AI key, if enabled) is still at its placeholder value — check `docker compose logs backend` for the exact `RuntimeError` message (section 4) |
| Login works but the user gets logged out on refresh/reload | HTTPS not actually configured yet — see section 5's "Secure cookie" enforcement note |
| `alembic upgrade head` can't connect | `DATABASE_URL` in `backend/.env.production` doesn't match `POSTGRES_PASSWORD` in `.env` (root) — see docker-compose.prod.env.example's note that these two must agree |
| 502 from nginx on `/api/v1/...` | `backend` container isn't healthy yet — check `docker compose ps` and `docker compose logs backend` |

**Rollback limitations**: this repository has no automated rollback
mechanism (no blue/green, no image tagging-by-version script). Rolling
back means: checking out the previous code revision, rebuilding
(`docker compose -f docker-compose.prod.yml build`), and redeploying —
and, if the new version's migrations are not safely reversible,
restoring the pre-migration backup (section 7) rather than attempting
`alembic downgrade`.

**Basic monitoring / disk space**: no monitoring/alerting stack is
included (matches the existing root `README.md`'s own documented
limitation — this sprint did not change that). At minimum, watch disk
usage on the Postgres volume and `database/backups/` (`df -h`,
`docker system df`), since an out-of-space Postgres container fails
writes silently from the application's point of view until you check.

## 9. What was actually validated (and what wasn't)

Executed in this working environment, not on a real server:

- `docker compose -f docker-compose.prod.yml config` — **succeeded**
  (exit 0), confirming the Compose file is syntactically valid, all
  variable interpolations resolve, and `postgres`/`redis` have no
  `ports:` mapping in the resolved config while `web` does (manually
  confirmed by reading the resolved output).
- `python -m pytest app/core/tests/ -q` (backend, after installing
  `requirements.txt` into this environment) — **58 passed, 1 skipped**.
- `python -m pytest app/ scripts/ -q` (full backend unit/mock suite) —
  **687 passed, 1 skipped**.
- `npm run test -- --run` (frontend) — **473 passed**.
- `npx tsc -b --noEmit` (frontend) — **0 errors**.
- `npm run lint` (frontend) — **0 errors, 5 pre-existing warnings**
  (unrelated to this sprint — see `README_SPRINT_89.md`).
- `npm run build` with `VITE_API_BASE_URL=/api/v1` — **succeeded**;
  manually confirmed the built bundle contains the literal `"/api/v1"`
  and zero occurrences of `localhost:8000`, i.e. the same-origin
  relative API base URL is actually what gets baked into production
  output.
- Manually reviewed every new/changed file in this sprint for
  hardcoded secrets, debug output, and consistency with
  `backend/app/core/config.py`'s real variable names — none of the
  `*.example`/compose/Dockerfile files contain a real credential.

**NOT executed — requires Docker (daemon unavailable in this
environment: the CLI is present, `docker info` fails to reach
`/var/run/docker.sock`) or a real server:**
- `docker compose -f docker-compose.prod.yml build` (an actual image
  build of `backend/Dockerfile.prod` and `frontend/Dockerfile`).
- `docker compose -f docker-compose.prod.yml up` (actually running the
  stack) and any health-check/`curl` verification against a live
  container.
- `nginx -t` (nginx's own config-syntax validator) against
  `nginx/nginx.conf` — reviewed manually instead; no nginx binary is
  installed in this environment.
- Any real HTTPS/certificate setup, real DNS, or a real domain.
- `scripts/backup_db.sh` / `scripts/restore_db.sh` against a real
  running Postgres container (both were syntax-checked with `bash -n`
  only).
- Real end-to-end login → refresh → logout behavior over HTTPS with
  the Secure-cookie enforcement actually exercised.

## 10. Known limitations

- No automated rollback, blue/green deploy, or canary mechanism.
- No monitoring/alerting/log-aggregation stack (matches the pre-existing
  root `README.md` limitation — not addressed here, out of this
  sprint's scope).
- `FILE_ENCRYPTION_KEY` rotation has no migration path (see section 8).
- Backup scheduling (the cron line in section 7) must be installed
  manually by the operator — nothing in this repository schedules it.
- No automated backup retention/pruning — `database/backups/` will grow
  unbounded unless the operator adds a cleanup step.
- The nginx config's HTTPS server block is provided commented-out with
  placeholder certificate paths, not a working TLS setup — see section
  5.
- `docker/` remains an empty placeholder (no reverse-proxy alternative
  or additional tooling was added there — everything needed lives in
  `nginx/`, the two Dockerfiles, and `docker-compose.prod.yml`).
- This document and the files it describes were prepared and statically
  validated, but **not deployed to or exercised against a real server**
  — see section 9's exact list of what that means concretely.
