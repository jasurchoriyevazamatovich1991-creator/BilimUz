# BilimUz — Sprint 89: Frontend Completion and UX Hardening

## 1. Project overview

BilimUz is a FastAPI (backend) / React + TypeScript (frontend) e-learning and testing platform. It covers user/role management, subjects/grades/topics/lessons, test authoring and delivery, scoring, certificates, notifications, AI Center, and more (27 backend feature modules).

**Sprint 89 is a frontend-only audit-and-fix sprint.** It inspected the complete frontend — routes, shared layout components, and loading/error/empty states — and fixed four confirmed defects found during that audit, each with its own regression tests. No AI provider changes, no backend contract changes, no database/auth changes, and no broad redesign were made.

> **Packaging note on this document's and this archive's scope**: at the time this archive was built, the repository's git history still ends at Sprint 67 (commit `449d316`); every sprint from 68 through 89 — including this one — exists only as **uncommitted working-tree changes** on top of that commit (149 changed/untracked entries in total; `git status --short | wc -l` confirms this). There is no isolated git commit or tag for "Sprint 89" to snapshot from. This archive and document therefore describe the **current working tree as a whole** — since the application is cumulative, that necessarily includes every earlier sprint's code needed to build and run it, with Sprint 89 being the newest layer. **One file is a known exception to a clean per-sprint boundary**: `frontend/src/routes/AppRoutes.tsx` carries three sprints' routing changes interleaved in one diff against the Sprint 67 baseline — Sprint 74 (admin exam-config route), Sprint 88 (student AI Center route), and Sprint 89 (the catch-all 404 route, added last in this sprint). A clean, Sprint-89-only version of this file could not be safely reconstructed without breaking working links elsewhere in the project (`TestsListPage.tsx` links to the exam-config route; `sidebarConfig.ts` references the AI Center route), so the archive includes the **full, current, cumulative file** rather than a disguised partial one. No commit or push was performed to create this package.

## 2. Sprint 89 changes

- **Catch-all 404 page and route**: a new `frontend/src/pages/public/NotFoundPage.tsx` renders a "Sahifa topilmadi" (page not found) message with a role-aware link back to the signed-in user's own panel (or `/` when signed out — resolved via `useAuthStore` + `resolvePanel`/`panelBasePath`). Wired in `AppRoutes.tsx` as a single top-level `<Route path="*">`, kept **last** in the route tree so it cannot shadow any real route, and placed outside any layout wrapper so it works for both authenticated and unauthenticated visitors. Before this sprint, an unmatched path rendered a blank screen.
- **Teacher dashboard query-error handling**: `frontend/src/pages/teacher/DashboardPage.tsx` previously had no `isError` handling on any of its four stat widgets (Topics/Lessons/Tests/Questions), so a failed request rendered identically to a genuinely empty (zero) count. Each widget now shows its own `ErrorState` on failure while the other three continue to show real data independently, and a toast fires via the now-exported `useToastOnQueryError` hook (`frontend/src/hooks/useDashboardStats.ts`).
- **Responsive sidebar drawer and hamburger navigation**: `frontend/src/components/layout/Sidebar.tsx` (shared by every authenticated layout — Student/Admin/Teacher) was a fixed `w-64` column with no responsive handling at all. It is now a slide-in drawer below the project's existing `lg` Tailwind breakpoint, toggled from a new hamburger button in `frontend/src/components/layout/Header.tsx`. The drawer closes on backdrop click, on Escape, or automatically after following a nav link. At `lg` and above, the sidebar's appearance is unchanged (always-visible sticky column). Toggle state lives in a new, deliberately non-persisted Zustand store, `frontend/src/store/uiStore.ts` (drawer state has no meaning across reload or a new tab).
- **Escape-to-close and initial focus in ConfirmDialog**: `frontend/src/components/common/ConfirmDialog.tsx` now closes on Escape (matching the header dropdown's existing convention) and moves focus to its Cancel button on open, so a keyboard-only user is never left blindly tab-cycling to dismiss it.
- **Tests**: 18 new/updated tests covering all four fixes — `NotFoundPage.test.tsx` (3), `AppRoutes.test.tsx` (3, exercising the real route tree, not a stub), `Sidebar.test.tsx` (6), `DashboardPage.test.tsx` for teacher (+2), `Header.test.tsx` (+1), `ConfirmDialog.test.tsx` (+3).

## 3. Requirements

Taken directly from the project's own manifests (`backend/Dockerfile`, `backend/requirements.txt`, `frontend/package.json`), not assumed:

- **Python 3.13** (`backend/Dockerfile`: `FROM python:3.13-slim`; local 3.11+ also works per the project's own README)
- **Node.js 20+** and npm (`frontend/package.json`: React 19 / Vite 6)
- **PostgreSQL 16** (`docker-compose.yml`: `postgres:16-alpine`)
- **Redis 7** (`docker-compose.yml`: `redis:7-alpine`)
- Key pinned backend dependencies (`backend/requirements.txt`): `fastapi==0.115.0`, `sqlalchemy==2.0.35`, `alembic==1.13.3`, `pydantic==2.9.2`, `argon2-cffi==23.1.0`, `pyjwt==2.9.0`, `redis==5.1.1`, `boto3==1.35.36`, `bleach==6.1.0`, `pytest==8.3.3`, `httpx==0.27.2`
- Frontend dependencies (`frontend/package.json`): React `19.x`, React Router `7.x`, TanStack Query `5.x`, Zustand `5.x`, Axios `1.x`, Tailwind CSS + shadcn/ui primitives, KaTeX; dev/test: Vite `6.x`, Vitest `2.x`, Testing Library, ESLint `9.x`

## 4. Frontend setup

```bash
cd frontend
npm install
cp .env.example .env    # VITE_API_BASE_URL — default: http://localhost:8000/api/v1
npm run dev
```

Vite's dev server runs on `http://localhost:5173` by default. The backend (section 5 below) must be running for any page that calls the API.

Production build:

```bash
npm run build     # tsc -b && vite build — output: frontend/dist/
npm run preview    # preview the built output locally
```

## 5. Backend setup

From the project's own root `README.md`:

**Via Docker Compose** (Postgres + Redis + backend together):

```bash
docker-compose up -d
```

**Or locally**:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # see section 6 below
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger UI is then available at `http://localhost:8000/docs`. `ENVIRONMENT` must be set in `.env` to one of `development`, `staging`, or `production` — the backend refuses to start without it (fail-closed; unrelated to this sprint, pre-existing behavior).

## 6. Configuration

Never put real secret values in this document or any other versioned file. Copy the example files and edit your own local copy:

- Backend: [`backend/.env.example`](backend/.env.example) — see the project's root `README.md` (section 8) for the full variable reference (`ENVIRONMENT`, `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET_KEY`, `FILE_ENCRYPTION_KEY`, `STORAGE_BACKEND`, `AI_PROVIDER`/`AI_API_KEY`, etc.). None of these variables were touched by Sprint 89.
- Frontend: [`frontend/.env.example`](frontend/.env.example) — one variable, `VITE_API_BASE_URL` (default `http://localhost:8000/api/v1`). Not touched by Sprint 89.

## 7. Testing commands and results

Run from `frontend/` on the date this archive was built:

```bash
npm run test -- --run
```
**Result: 69 test files, 473 tests, all passed.**

## 8. Build and lint commands and results

```bash
npx tsc -b --noEmit
```
**Result: 0 errors.**

```bash
npm run lint
```
**Result: 0 errors, 5 pre-existing warnings** — all in files Sprint 89 did not touch (`LessonFormPage.tsx`, `QuestionFormPage.tsx`, `TestFormPage.tsx`, `TopicFormPage.tsx`: missing-`useEffect`-dependency warnings; `AttemptPage.tsx`: one unused-eslint-disable-directive warning). None were introduced or modified by this sprint; none were silenced to make this report look cleaner.

```bash
npm run build
```
**Result: build succeeded** (one pre-existing Vite chunk-size advisory for the main JS bundle, unrelated to this sprint's changes).

## 9. Known limitations

- **Responsive behavior was checked using automated jsdom tests, not manually in a real browser.** `Sidebar.test.tsx` asserts on the Tailwind classes that drive the breakpoint behavior (`-translate-x-full` vs `translate-x-0`, backdrop presence), not on rendered layout at real viewport widths. No manual cross-browser or real-device check was performed.
- **`AttemptPage` (the test-taking page) still uses the regular `StudentLayout`** and was not changed in this sprint. It inherits the sidebar/header responsive changes only incidentally through the shared layout; a dedicated full-screen exam shell remains future work.
- **No formal WCAG audit was performed.** The fixes in this sprint address specific, concrete keyboard/focus gaps found during the audit (Escape-to-close and focus-on-open in `ConfirmDialog`, Escape-to-close in the sidebar drawer); they are not a comprehensive accessibility review.
- The mobile-nav hamburger button toggles the drawer but does not carry `aria-expanded`/`aria-controls` attributes — a smaller refinement left out as a new feature outside this sprint's narrow audit-and-fix scope.
- ESLint's five pre-existing warnings (section 8) remain unaddressed, as confirmed by this sprint's own validation run — fixing them was out of scope (no dependency or unrelated-code changes were made just to silence pre-existing warnings).

## 10. Archive contents, exclusions, and extraction

This ZIP is a **cumulative project snapshot** based on the current working tree, not a repository containing only Sprint 89 code — see the packaging note in section 1 for the one exception (`AppRoutes.tsx`) to a clean per-sprint boundary.

**Included**: the full backend source (`app/`, `alembic/`, `scripts/`, `conftest.py`, `requirements.txt`, `Dockerfile`, `.env.example`, `backend/README.md`), the full frontend source (`src/`, `public/`, `package.json`, `package-lock.json`, `.env.example`, config files, `frontend/README.md`), `docs/` (including `docs/releases/SPRINT_89_RELEASE_NOTES.md`), `database/schema/schema_v2.sql`, `docker-compose.yml`, `nginx/`/`docker/`/`scripts/` (currently empty, `.gitkeep` only), `.github/workflows/`, and this README.

**Excluded** (per the project's own documented release-packaging conventions, `docs/RELEASE_PACKAGING.md`): `.git/` history, `backend/.env` (real secrets — `.env.example` is included instead), `backend/venv/`/`.venv/`, `**/__pycache__/*` and `*.pyc`, `**/.pytest_cache/*`, `backend/storage/uploads/*` (any locally stored user files), `frontend/node_modules/*`, `frontend/dist/*` (build output, regenerated by `npm run build`), `database/backups/*` (real DB dumps, if any), `*.log`, `frontend/tsconfig.*.tsbuildinfo`, `*.DS_Store`, and any nested `*.zip` (including this archive's own prior versions for other sprints).

**Extraction**:
```bash
unzip BilimUz-Sprint-89.zip
cd BilimUz
```
Then follow sections 4 and 5 above to set up the frontend and backend.

## 11. Repository and license

GitHub repository: https://github.com/jasurchoriyevazamatovich1991-creator/BilimUz

**License**: the repository's root `LICENSE` file exists but is **empty** — no license has actually been specified for this project. This document does not assume or invent one (e.g., MIT, Apache-2.0); treat the project as unlicensed/all-rights-reserved by default until the repository owner adds real license text.
