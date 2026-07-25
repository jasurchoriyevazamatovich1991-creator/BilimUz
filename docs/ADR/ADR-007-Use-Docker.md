# ADR-007

## Title
Use Docker for local development and deployment

## Status
Accepted, **implemented** — `backend/Dockerfile` and root `docker-compose.yml` are real and runnable (Postgres + Redis + backend, `docker-compose up --build`). `nginx/` reverse-proxy config remains a placeholder until the frontend has real content to serve.

## Context
BilimUz's stack has four runtime dependencies that must run identically across every developer's machine and every environment (staging, production): FastAPI backend, React frontend (built to static files), PostgreSQL, and Redis. Without containerization, "works on my machine" schema/dependency drift is a near-certainty across a multi-year, multi-developer project — especially with PostgreSQL-specific types (`UUID`, `INET`, `JSONB`) that don't behave identically across local installs and CI.

## Decision
Use **Docker** (one `Dockerfile` per service: `backend`, `frontend`) orchestrated with **docker-compose** for local development, with **Nginx** as the reverse proxy in front of both services in production (serving the built frontend as static files, proxying `/api/*` to the backend).

## Consequences

**Positive:**
- A new developer runs `docker-compose up` and gets an identical Postgres + Redis + backend + frontend stack — no "install Postgres 16.3 exactly" onboarding friction.
- CI can run the exact same containers used in production, so "tests passed in CI" and "works in production" stop being different claims — directly closes part of the Senior Review's Testing gap (tests need a real Postgres to run against; Docker is how CI will provide one).
- Nginx in front of both services means the frontend and backend can scale independently later (separate container replicas) without an architecture change.

**Negative:**
- Adds an operational layer (image builds, registry, orchestration) that a single-server deployment doesn't strictly need at very small scale — accepted because BilimUz's stated target ("millions of users") makes this investment pay off early rather than requiring a painful retrofit later.
- Currently a known gap: none of `docker/`, `nginx/`, `docker-compose.yml` have real content yet. This ADR records the *decision*; `docs/Deployment/` (not yet written) will record the *implementation*.

## Alternatives

| Option | Rejected because |
|---|---|
| Bare-metal / manual server setup | Fragile, hard to reproduce, no clean path to horizontal scaling |
| Kubernetes from day one | Justified eventually at "millions of users" scale, but premature before a single container image exists; Docker Compose is the correct first step, K8s is a documented later migration, not a v1.0 requirement |
| Serverless (e.g. AWS Lambda for the API) | FastAPI + SQLAlchemy with persistent DB connections doesn't fit the serverless cold-start/connection-pooling model well; rejected for this stack |

## References
- `.cursor/prompts/01-architect.md` ("Docker", "Nginx")
- `docs/00_Folder_Architecture.md` (`docker/`, `nginx/`, `docker-compose.yml`)
- Senior Review Action Plan, item 7
