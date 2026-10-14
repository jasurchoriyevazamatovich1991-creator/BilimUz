# BilimUz — Sprint 88: Real AI Provider Integration

## 1. Project overview

BilimUz is a FastAPI (backend) / React + TypeScript (frontend) e-learning and testing platform. It covers user/role management, subjects/grades/topics/lessons, test authoring and delivery, scoring, certificates, notifications, and an AI Center.

Before Sprint 88, the AI Center module (`backend/app/modules/ai/`) existed only as an honest, vendor-agnostic interface: every AI endpoint always returned `501 Not Implemented` because no real AI provider was wired in, and no AI chat UI existed on the frontend at all.

**Sprint 88 adds a real, working AI provider integration** — the Anthropic Claude Messages API — behind the same interface, plus a minimal student-facing chat page that uses it. When no provider is configured, the system still honestly returns `501`; it never fabricates a response.

> **Packaging note on this document's scope**: at the time this archive was built, the repository's git history ends at Sprint 67 (commit `449d316`); Sprints 68–88, including this one, exist only as **uncommitted working-tree changes** on top of that commit (134 changed/untracked files in total; `git status --porcelain | wc -l` confirms this). There is no isolated git commit or tag for "Sprint 88" to snapshot from. This archive and document therefore describe the **current working tree as a whole** — which, since the application is cumulative, necessarily includes every earlier sprint's code needed to run it — with Sprint 88 being the newest layer (the AI provider integration and AI Center page). No commit or push was performed to create this package.

## 2. Sprint 88 features

- **Anthropic Claude Messages API integration** (`backend/app/modules/ai/providers.py`, class `AnthropicProvider`): calls `https://api.anthropic.com/v1/messages` directly via `httpx.post()` (no vendor SDK dependency added). Sends the API key only in the `x-api-key` header, never in the request body, logs, or any exception message.
- **`AI_PROVIDER` configuration** (`backend/app/core/config.py`): `none` (default) or `anthropic`. Provider selection is a pure function, `select_ai_provider()` (`backend/app/modules/ai/dependencies.py`): it returns the real `AnthropicProvider` only when `AI_PROVIDER=anthropic` **and** `AI_API_KEY` is not the public placeholder value; otherwise it always falls back to the pre-existing `UnconfiguredAIProvider`, which raises a 501 — a missing or placeholder key can never reach a real API call.
- **`AI_API_KEY`, `AI_MODEL`, `AI_MAX_OUTPUT_TOKENS`, `AI_REQUEST_TIMEOUT_SECONDS`** — new settings in `Settings` (`backend/app/core/config.py`), all with safe public defaults (`AI_API_KEY` defaults to the placeholder `CHANGE_ME_IN_PRODUCTION`; `AI_MODEL` defaults to `claude-3-5-haiku-20241022`; `AI_MAX_OUTPUT_TOKENS` defaults to `1024`; `AI_REQUEST_TIMEOUT_SECONDS` defaults to `30.0`). In `production`/`staging`, startup is refused if `AI_PROVIDER=anthropic` and `AI_API_KEY` is still the placeholder (`validate_production_secrets()`, same fail-closed pattern already used for `JWT_SECRET_KEY`/`FILE_ENCRYPTION_KEY`/R2 settings).
- **Student AI chat endpoint and ownership verification**: `POST /api/v1/ai/chats/{chat_id}/messages` (plus `POST /api/v1/ai/chats`, `GET /api/v1/ai/chats/me`, `GET /api/v1/ai/chats/{chat_id}`) — all require authentication, and `AIChatService` raises `ChatNotFoundException` (404) if the chat does not belong to the requesting user.
- **Message length and rate limits**: message content is capped at `MAX_MESSAGE_LENGTH = 4000` characters (`backend/app/modules/ai/constants.py`, validated in `validators.py` before the provider is ever called), and `POST /chats/{chat_id}/messages` is rate-limited to 10 requests per 60 seconds per user via the pre-existing `rate_limit_by_user()` dependency (Redis-backed).
- **Provider error handling and manual retry behavior**: every provider failure mode (`AIProviderNotConfiguredException` → 501, `AIProviderAuthenticationException` → 502, `AIProviderRateLimitedException` → 429, `AIProviderTimeoutException` → 504, `AIProviderUnavailableException` → 503) is caught uniformly by `AIChatService.send_message()`, which has already saved the user's own message before calling the provider — so a failed provider call never loses what the user typed. The frontend (`useSendAiMessage` in `frontend/src/hooks/useAi.ts`) does **not** auto-retry a failed send; it shows the real error and a manual "Qayta urinish" (Retry) button.
- **Frontend AI Center route and current limitations**: `frontend/src/pages/student/AiCenterPage.tsx`, mounted at `/student/ai` (Applicant/Student panel only). It reuses the user's most recent existing chat if one exists (`GET /ai/chats/me`) or starts a new one; shows the full message history; lets the user send a new message with a client-side 4000-character check; shows loading and error states; never claims to stream a response (the backend returns one complete reply per request).
- **The admin AI page remains a placeholder** — confirmed in `frontend/src/routes/AppRoutes.tsx`: `/admin/ai` is still rendered by the generic `<PlaceholderPage>` via `placeholderRoutesFor(ADMIN_ITEMS, "/admin", [...])`, and `/admin/ai` is not in that function's exclusion list. No backend admin-facing AI feature exists to wire it to; this was an explicit, approved scope decision, not an oversight.

## 3. Requirements

Taken directly from the project's own manifests and CI configuration (`backend/Dockerfile`, `backend/requirements.txt`, `.github/workflows/*.yml`), not assumed:

- **Python 3.13** (`backend/Dockerfile`: `FROM python:3.13-slim`; CI: `python-version: "3.13"`)
- **PostgreSQL 16** (`docker-compose.yml`: `postgres:16-alpine`)
- **Redis 7** (`docker-compose.yml`: `redis:7-alpine`) — required for rate limiting and refresh-token/CSRF flows, and for the integration test suite
- **Node.js 20** (CI: `node-version: "20"`)
- Key pinned Python dependencies (`backend/requirements.txt`): `fastapi==0.115.0`, `sqlalchemy==2.0.35`, `alembic==1.13.3`, `pydantic==2.9.2`, `httpx==0.27.2` (the library used for the new Anthropic calls — already a dependency before this sprint, no new package added), `pytest==8.3.3`
- Frontend: `package.json`/`package-lock.json` (React, TypeScript, Vite, TanStack Query, Tailwind, Vitest)

## 4. Installation and configuration

### Development setup — backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# edit .env — see section 5 below for the AI_* variables specifically
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

`ENVIRONMENT` must be set in `.env` to one of `development`, `staging`, or `production` — there is no default; the app refuses to start without it (fail-closed, confirmed in `backend/app/core/config.py` and its tests).

### Development setup — frontend

```bash
cd frontend
npm install
cp .env.example .env     # sets VITE_API_BASE_URL, default http://localhost:8000/api/v1
npm run dev
```

### Database migrations and Redis

```bash
# PostgreSQL 16 and Redis 7 required (local install or Docker — see docker-compose.yml)
cd backend
alembic upgrade head          # applies all 19 migrations under alembic/versions/
```

Redis is required for rate limiting (including the new AI message rate limit) and the refresh-token/CSRF flow; the app's own README notes it is not optional in a real run.

### Development vs. production

This repository's documented production readiness is explicitly limited (see `README.md` section 11, "Production deployment bo'yicha mavjud cheklovlar"): there is no automated deployment pipeline, no load testing, and no production monitoring set up. For a production-like run, set `ENVIRONMENT=production` or `staging`, which activates fail-closed validation of `JWT_SECRET_KEY`, `FILE_ENCRYPTION_KEY`, and (if applicable) `AI_API_KEY` / `R2_*` — the app refuses to start if any of these are still at their public placeholder values. Development mode (`ENVIRONMENT=development`) does not enforce this.

## 5. Anthropic API configuration

- **Where to obtain a key**: create an account at `https://console.anthropic.com/`, then generate an API key under its API Keys settings. **This key is never included in this repository or this archive** — only placeholder examples appear in `.env.example`.
- **Where to configure it**: `backend/.env` (never commit this file — it is `.gitignore`d). Set:
  ```
  AI_PROVIDER=anthropic
  AI_API_KEY=<your real key>
  AI_MODEL=claude-3-5-haiku-20241022   # or another Anthropic Messages API model
  AI_MAX_OUTPUT_TOKENS=1024
  AI_REQUEST_TIMEOUT_SECONDS=30
  ```
- **`AI_PROVIDER=none`** (the default, and what is actually committed in `.env.example`) **disables the external provider entirely** — the AI message endpoint then always returns `501 Not Implemented`, and `AI_API_KEY` is never read or sent anywhere.
- Leaving `AI_API_KEY` at its placeholder value while setting `AI_PROVIDER=anthropic` is also safe: `select_ai_provider()` detects the placeholder and still falls back to the honest 501 behavior rather than attempting (and failing) a real call.
- **Never commit a real key.** `.env` is excluded from version control and from this archive; only `.env.example` (placeholders only) is distributed.

## 6. API usage

Verified directly against `backend/app/modules/ai/router.py` and `backend/app/modules/ai/schemas.py` — not invented.

**`POST /api/v1/ai/chats/{chat_id}/messages`** — send a message and get an AI response.

- **Authentication**: required (`Authorization: Bearer <access_token>`); the authenticated user must own the chat (otherwise 404).
- **Rate limit**: 10 requests / 60 seconds per authenticated user.
- **Request body**:
  ```json
  { "content": "string, 1–4000 characters" }
  ```
- **Response body** (wrapped in the project's standard envelope `{success, message, data, errors}`), `data` is:
  ```json
  {
    "chat_id": "uuid",
    "user_message": { "id": "uuid", "chat_id": "uuid", "role": "user", "message": "string", "created_at": "datetime" },
    "assistant_message": { "id": "uuid", "chat_id": "uuid", "role": "assistant", "message": "string", "created_at": "datetime" }
  }
  ```
- **Error responses**: `422` (empty/oversized message, fails validation before the provider is called), `401` (not authenticated), `404` (chat does not belong to the user), `429` (rate limit exceeded, by this endpoint's own limiter, or `AIProviderRateLimitedException` from the provider), `501` (no provider configured), `502` (provider authentication failure, or a generic provider error), `503` (provider unreachable/unavailable), `504` (provider request timed out).

Other endpoints in the same module, unchanged in contract this sprint: `POST /api/v1/ai/chats` (start a chat, optional `title` query parameter), `GET /api/v1/ai/chats/me` (paginated list), `GET /api/v1/ai/chats/{chat_id}` (chat + full history).

## 7. Testing and validation

All of the following were **actually executed during this packaging task or the Sprint 88 implementation task in this same session**, against the real local sandbox services (not claimed from memory):

| Check | Command | Prerequisite | Result |
|---|---|---|---|
| Backend unit/mock tests | `pytest app/ scripts/ -q` (from `backend/`) | None (no DB/Redis) | 687 passed, 1 skipped |
| Backend integration tests | `pytest tests/integration/ -q` (from `backend/`) | Real PostgreSQL (`TEST_DATABASE_URL`, DB name must end `_test`) and real Redis (`TEST_REDIS_URL`, DB index not 0/1) | 338 passed |
| Frontend unit tests | `npm run test -- --run` (from `frontend/`) | None | 455 passed |
| Frontend type check | `npx tsc -b --noEmit` (from `frontend/`) | None | 0 errors |
| Frontend lint | `npm run lint` (from `frontend/`) | None | 0 errors, 5 pre-existing warnings unrelated to this sprint |
| Frontend production build | `npm run build` (from `frontend/`) | None | Succeeds |
| OpenAPI schema generation | `pytest app/core/tests/test_openapi_schema_generation.py -v` (from `backend/`) | None | 5 passed |

None of these runs used a real Anthropic API key — every AI-provider test mocks `httpx.post` directly or overrides the provider dependency with an in-test fake; this packaging task did not re-run them a second time beyond what is listed above, since they were already run and verified in the implementation task immediately preceding this one in the same session.

## 8. Security notes

- The Anthropic API key is read only from backend environment configuration (`AI_API_KEY` in `.env`) and is used only inside `backend/app/modules/ai/providers.py`; it is never sent to, or readable from, the frontend/browser.
- No secret values are stored in this repository or in this archive — `backend/.env` is excluded from both; only `backend/.env.example` (placeholders) is included.
- Every AI endpoint requires authentication; `AIChatService` enforces per-chat ownership (a user cannot read or post into another user's chat — returns 404).
- Rate limiting: 10 requests/60s per user on the message-send endpoint (pre-existing `rate_limit_by_user()` mechanism, reused unchanged).
- Timeout: every provider call is bounded by `AI_REQUEST_TIMEOUT_SECONDS` (default 30s); a hang becomes a `504`, not an indefinite wait.
- Output length: bounded by `AI_MAX_OUTPUT_TOKENS` (default 1024), passed through to the Anthropic API's own `max_tokens` parameter.
- No automatic retries anywhere in this feature (service layer or frontend) — a failed call surfaces once and requires an explicit retry, so a provider outage cannot silently multiply request volume or cost.
- In `production`/`staging`, the app refuses to start if `AI_PROVIDER=anthropic` and `AI_API_KEY` is still its public default placeholder (fail-closed; same mechanism already applied to `JWT_SECRET_KEY`/`FILE_ENCRYPTION_KEY`/R2 credentials).

## 9. Known limitations

- **No streaming** — the backend returns one complete response per request; the frontend never claims otherwise.
- **Chat persistence/reloading**: which chat is "active" on the frontend is resolved fresh on every page load (most recent chat, or a newly created one) and is not cached in browser storage; message history itself is fully persisted server-side and reloads correctly.
- **Admin AI page status**: `/admin/ai` remains an unwired `PlaceholderPage` — confirmed in `frontend/src/routes/AppRoutes.tsx`. No backend admin-AI feature exists.
- **Anthropic-only provider support**: `select_ai_provider()` currently recognizes only `none` and `anthropic`; no other vendor is implemented this sprint.
- **No real-provider verification possible in this environment**: since no real `AI_API_KEY` was supplied, the real Anthropic API has never actually been called in this project to date — all verification is against mocks/fakes, as documented in section 7.
- Anthropic's own rate limits, quotas, and billing are governed entirely by Anthropic's account/plan and are not simulated, enforced, or guaranteed by this codebase.

## 10. Archive contents

**File**: `BilimUz-Sprint-88.zip`

**Included**: the full backend (`app/`, `alembic/` with all 19 migrations, `scripts/`, `tests/`, `conftest.py`, `requirements.txt`, `Dockerfile`, `.env.example`), the full frontend source (`src/`, `public/`, `package.json`, `package-lock.json`, `.env.example`, config files — excluding generated output), `docs/` (architecture notes, API blueprint, sprint history), `database/schema/`, `docker-compose.yml`, `.github/workflows/` (all three CI workflows), the root `README.md`, and this document.

**Excluded** (same convention as `docs/RELEASE_PACKAGING.md`, verified empty/absent by extracting and inspecting the archive before this report was written):
- `.git/` (full commit history — not needed for a source snapshot)
- Any real `backend/.env` (confirmed: none present in the archive — only `.env.example`)
- `backend/venv/`, `backend/.venv/`, `**/__pycache__/`, `*.pyc`, `**/.pytest_cache/`
- `frontend/node_modules/`, `frontend/dist/`, `frontend/.vite/`, `frontend/tsconfig.*.tsbuildinfo`
- `backend/storage/uploads/*` (local-disk user uploads, if any — none were present)
- `database/backups/*` (DB dump files, if any — none were present)
- `*.log`, `*.DS_Store`, pre-existing sibling release ZIPs at the repository root

**To extract**:
```bash
unzip BilimUz-Sprint-88.zip
```
This produces a `BilimUz/` directory with the full project structure preserved.

## 11. Troubleshooting

- **Backend refuses to start with a configuration error mentioning `ENVIRONMENT`**: this variable has no default and must be explicitly set in `backend/.env` to `development`, `staging`, or `production`.
- **AI message endpoint always returns `501 Not Implemented`**: this is the correct, honest behavior when `AI_PROVIDER=none` (the default) or when `AI_API_KEY` is still the placeholder — set both `AI_PROVIDER=anthropic` and a real `AI_API_KEY` to enable real responses (section 5).
- **AI message endpoint returns `502`**: the configured Anthropic API key was rejected — verify it is current and correctly copied into `AI_API_KEY`.
- **AI message endpoint returns `504`**: the request to Anthropic exceeded `AI_REQUEST_TIMEOUT_SECONDS` — check network connectivity to `api.anthropic.com`, or raise the timeout if the model/prompt legitimately needs more time.
- **AI message endpoint returns `429` on your own requests**: either the per-user rate limit (10/60s) or Anthropic's own rate limiting was hit — wait and retry manually; the frontend does not auto-retry by design.
- **Integration tests fail or are skipped**: they require real `TEST_DATABASE_URL` (a PostgreSQL database whose name ends in `_test`) and `TEST_REDIS_URL` (a Redis database index other than 0 or 1) to be set — these are safety guards against accidentally running tests against a real/dev database.
- **`npm run lint` or `tsc -b --noEmit` reports errors unrelated to the AI feature**: at the time this archive was built, lint showed 0 errors (5 pre-existing warnings in unrelated files) and typecheck showed 0 errors — if your checkout differs, compare against a clean `npm install`.

## 12. License and project links

**No usable license text was found.** A file named `LICENSE` exists at the repository root, but it is **empty (0 bytes)** — confirmed directly (`wc -c LICENSE` → `0`). This document does not assume or invent any license terms on the project's behalf; anyone redistributing this archive should treat its licensing status as unresolved until the repository owner adds real license text.

**Repository**: `https://github.com/jasurchoriyevazamatovich1991-creator/BilimUz`
