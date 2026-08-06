# Sprint 13 — Frontend Architecture Impact Analysis: Foundation

**Status: DESIGN ONLY — no code written, no repository files modified, no ZIP.**

This is the first frontend-touching sprint of the project. Everything below was grounded in what already exists — `frontend/`'s empty scaffold (`api, assets, components, hooks, layouts, pages, routes, services, store, styles, utils`), `.cursor/context/04-tech-stack.md` (React 19+/TypeScript/Tailwind/shadcn-ui, decided but unbuilt), and `docs/UI-UX/panel_modules.md` + `ui_ux_blueprint.md` (role navigation and the test-taking screen already sketched during Sprint 1 planning, never touched since). Nothing here contradicts that prior planning — it's built on top of it.

---

## 1. Frontend Architecture

**Vite + React 19 + TypeScript**, matching the tech-stack decision already on record. The backend's own layering discipline (Router → Service → Repository) has an honest frontend analogue, and this sprint adopts it explicitly rather than inventing something unrelated:

| Backend concept | Frontend equivalent |
|---|---|
| Router (HTTP layer) | Page component (route-level) |
| Service (business logic) | Custom hook (`useXState`, `useXMutation`) |
| Repository (data access) | API client module (`src/api/`) |
| Schema (Pydantic) | TypeScript interface/type (`src/types/`) |
| `core/` (shared infra) | `src/utils/`, `src/hooks/` (shared, cross-feature) |

**Server state vs. client state — a real, necessary decision (Outstanding Decision #1)**: React itself has no opinion on this, and getting it wrong here would be the frontend equivalent of the backend's "no new architectural layers" violations already caught and fixed multiple times. Recommended: **TanStack Query** (server state — API data, caching, refetching, loading/error states) + **Zustand** (client state — current user, UI preferences) as two genuinely different concerns, not one library doing both badly. This mirrors the backend's own split between `repository.py` (data access) and in-memory request state.

## 2. React Folder Structure

The existing empty scaffold (`api, assets, components, hooks, layouts, pages, routes, services, store, styles, utils`) is **kept exactly as-is** — Sprint 13 fills it in, doesn't restructure it (same "don't touch what's already decided" discipline as reusing `AuditLog` instead of redefining it in Sprint 12).

```
frontend/src/
├── api/            — one file per backend module (auth.ts, users.ts, tests.ts...),
│                      mirrors backend/app/modules/ one-to-one, each just wraps the
│                      shared HTTP client with typed request/response functions
├── assets/          — images, icons (existing, empty)
├── components/        — shared, reusable UI (Button, Card, DataTable...) —
│                         shadcn/ui-based, NOT feature-specific
├── hooks/               — useAuth, useTokenRefresh, usePermission, and
│                           TanStack Query hooks per API module (useTests, useProfile...)
├── layouts/               — AdminLayout, TeacherLayout, StudentLayout, PublicLayout
│                             (see Section 7 — one per panel_modules.md role group)
├── pages/                   — route-level components, organized by role:
│                               pages/admin/, pages/teacher/, pages/student/, pages/public/
│                               (matches panel_modules.md's own role grouping exactly)
├── routes/                    — route definitions + the role-based guard (Section 3)
├── services/                    — NOT duplicated with api/ — this holds cross-cutting
│                                   logic that isn't a direct API wrapper (e.g. token
│                                   storage strategy, Section 6)
├── store/                        — Zustand stores (auth store, UI store)
├── styles/                        — Tailwind config, global CSS
├── utils/                          — pure functions (formatters, validators — mirrors
│                                       backend's validators.py convention exactly)
└── types/                          — NEW folder, not in the current scaffold — TypeScript
                                        interfaces generated/hand-mirrored from backend
                                        Pydantic schemas (Outstanding Decision #2: manual
                                        vs. OpenAPI-codegen, see Section 5)
```

**One new top-level folder proposed** (`types/`) beyond what's already scaffolded — flagged explicitly rather than silently added, same discipline as every backend Outstanding Decision.

## 3. Routing

**React Router v7** (the current major version as of React 19 compatibility). Structure:

```
/                          — Public: landing page
/login, /register, /verify   — Public: auth flow (Section 4)
/certificates/verify/:code     — Public: matches the existing PUBLIC backend
                                  endpoint GET /certificates/verify/{code} exactly —
                                  no auth wrapper needed, consistent with the backend's
                                  own "this is deliberately public" design
/admin/*                        — Protected: Admin, Super Admin only
/teacher/*                        — Protected: Teacher only
/student/*                          — Protected: Student, Applicant only
```

**Role-based route guarding** happens at the layout level, not per-page — an `<AdminLayout>` wrapping `/admin/*` checks the role once; individual admin pages don't each re-check. This mirrors the backend's `require_roles()` dependency pattern: declared once at the router/endpoint boundary, not scattered through service logic.

## 4. Authentication Flow

Maps directly onto the **existing, unmodified** `auth` module (Sprint 4's Auth Cutover — `/auth/register`, `/auth/verify`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me`) and the already-documented UX in `ui_ux_blueprint.md`:

```
Login page (phone/email + password)
  → POST /auth/login → {access_token, refresh_token}
  → store tokens (Section 6) → GET /auth/me → role known
  → redirect to role's dashboard (Section 9)

Register page → POST /auth/register → {user_id, debug_code}
  → Verify page (6-digit code, auto-focus per ui_ux_blueprint.md)
  → POST /auth/verify → redirect to Login
```

**A real, known backend constraint surfaces here (Outstanding Decision #3)**: `POST /auth/register` currently returns `debug_code` directly in the response body (documented in `auth/README.md` as a placeholder for real SMS delivery — the `notifications` module exists but isn't wired to `auth`, per Sprint 8's own README). The frontend Verify page **will work correctly either way** (it just submits whatever 6-digit code the user has), but until real SMS delivery exists, `debug_code` from the register response is the only way to actually get the code during testing/demo. This isn't a frontend problem to solve — flagged so it isn't rediscovered as a "bug" later.

## 5. API Client

One shared HTTP client (likely `axios` or the native `fetch` wrapped once — Outstanding Decision #4), consumed by per-module files in `src/api/`. Every response is unwrapped once, centrally, matching the backend's **single, universal envelope** (`{success, message, data, errors}` — `core/schemas.py::success_response()`, unchanged since Sprint 1):

```typescript
// One place decodes the envelope — every api/*.ts file just returns `data`
async function apiRequest<T>(...): Promise<T> {
  const response = await httpClient(...);
  if (!response.data.success) throw new ApiError(response.data.message, response.data.errors);
  return response.data.data;
}
```

**Type source (Outstanding Decision #2, expanded)**: the backend's OpenAPI schema is fully real (every endpoint has `response_model`-equivalent shape via the wrapped envelope — though recall the backend audit's Medium finding: no `response_model=` is set anywhere, so autogenerated types would only know the wrapper shape, not `data`'s real contents, unless each `*Out` Pydantic schema is separately introspected). Given that gap, **hand-written TypeScript interfaces mirroring each `*Out` schema** (in `types/`) is the pragmatic Sprint 13 choice over OpenAPI codegen — codegen would need the `response_model=` gap closed first to be useful, which is out of this sprint's scope.

## 6. Token Refresh

The backend issues a **15-minute access token + 30-day refresh token** (unchanged since Sprint 1, `ACCESS_TOKEN_EXPIRE_MINUTES=15`). The frontend must handle silent refresh transparently:

```
Every API call:
  → attach access_token as Bearer header
  → if response is 401 (InvalidTokenException, expired):
      → call POST /auth/refresh with refresh_token (rotates — backend's refresh
        endpoint issues a NEW refresh_token every time, per Sprint 4's unchanged
        rotation logic)
      → retry the original request once with the new access_token
      → if refresh itself fails (refresh_token also expired/revoked): force logout
```

**Storage location is a real security decision (Outstanding Decision #5)**: `localStorage` (simple, vulnerable to XSS token theft) vs. an `httpOnly` cookie (safer, but requires backend changes — `auth/router.py`'s login/refresh endpoints would need to *set* cookies, not just return tokens in the JSON body, which the backend currently doesn't do and wasn't asked to change this sprint). Given "no backend changes" is implicit in a frontend-only sprint, the practical Sprint 13 default is `localStorage` with the explicit, stated risk — same "documented risk, not hidden" practice used for every backend security trade-off (e.g. `FILE_ENCRYPTION_KEY` loss risk in Sprint 8).

## 7. Layout

Four layouts, matching `ui_ux_blueprint.md`'s existing role-navigation map exactly (`Super Admin/Admin → Admin Panel`, `Teacher → Teacher Panel`, `Applicant/Student → Student Panel`, unauthenticated → `Public`):

- `PublicLayout` — header (logo, nav, login/register buttons) + footer, no sidebar.
- `AdminLayout` — sidebar (Section 8) + top bar (user menu, notifications icon) + content area.
- `TeacherLayout` — same shell as Admin, different sidebar content.
- `StudentLayout` — same shell, different sidebar content; **the test-taking screen (`ui_ux_blueprint.md` §4.3) explicitly does NOT use this layout** — it's a dedicated full-screen layout with no sidebar/header chrome (the timer replaces the header), consistent with how the blueprint already describes it. Flagged here so it isn't accidentally wrapped in the standard `StudentLayout` later.

## 8. Sidebar

Directly reuses the **already-authored** navigation lists in `docs/UI-UX/panel_modules.md` — not redesigned, just implemented:

| Role | Sidebar items (from panel_modules.md, unchanged) |
|---|---|
| Admin | Dashboard, Users, Roles, Permissions, Subjects, Grades, Topics, Lessons, Tests, Questions, Results, Certificates, Analytics, Payments, Notifications, AI, Settings |
| Teacher | Dashboard, Attestatsiya, Milliy Sertifikat, Testlar, Natijalar, Statistika, Profil |
| Applicant | Dashboard, DTM, Blok Test, Mavzular, Natijalar, Reyting, AI Ustoz, Profil |
| Student | Dashboard, Mening fanlarim, Darslar, Testlar, Natijalar, Yutuqlar, Profil |

**Sprint 13 builds the sidebar shell and navigation only** — each item links to a route that, this sprint, renders a placeholder page (Section 12 scope). Wiring each item to its real feature (e.g. a working Users CRUD table) is future-sprint work, matching the backend's own "framework this sprint, integration later" pattern (Sprint 8/9's provider interfaces, Sprint 12's `system_logs`).

## 9. Dashboard

One composable `<DashboardShell>` (cards grid, matches `ui_ux_blueprint.md` §4.1's "Faol testlar / So'nggi natijalar / Tavsiya etilgan mavzular" card-row pattern), with **role-specific content components** slotted in:

- Admin dashboard: platform-wide counts (users, tests, active attempts) — reads `analytics`/`users`/`tests` endpoints.
- Teacher dashboard: their own content's stats.
- Student/Applicant dashboard: their own progress, recommendations (would read `ai_recommendations` — but recall `ai`'s README: nothing generates a recommendation yet, no real provider exists, so this widget would legitimately show an empty state this sprint, not fake data).

**Sprint 13 scope is the shell + empty/loading states only** — real data-driven widgets need working list/detail pages first (out of scope, see Section 12).

## 10. RBAC UI

Two layers, mirroring the backend's own two-layer RBAC (`require_roles()` at the endpoint, ownership checks inside the service):

1. **Route-level**: a role isn't in the allowed set for a layout → redirect to their own dashboard or a 403 page (never a blank screen).
2. **Component-level**: a `usePermission()`/`useRole()` hook conditionally renders UI elements (e.g. an "Delete" button only for Admin) — this is **UI convenience, not security** — the backend's `require_roles()` remains the actual enforcement, exactly as the backend audit already established for the API layer (never trust the client). Stated explicitly so this distinction isn't lost when writing the actual code later.

**A real backend fact shapes this (Outstanding Decision #6)**: the backend currently has exactly the roles seeded in Sprint 1 — no `School Admin`/`Learning Center Admin` (explicitly not introduced in Sprint 11's `profiles` work). The frontend's role-based routing this sprint should therefore only branch on the roles that **actually exist**: `Super Admin, Admin, Teacher, Student, Applicant` (and whatever the remaining seeded roles are) — not pre-build UI for roles that don't exist yet.

## 11. Test Strategy

**Vitest + React Testing Library** — the standard pairing for a Vite project, same "boring, correct, already-proven" reasoning used for the backend's `cryptography`/Fernet choice in Sprint 8. Scope for Sprint 13 specifically:

- Auth flow: login form validation, token-refresh interceptor logic (mocked HTTP), redirect-on-401 behavior.
- Route guard: role-based redirect logic (unit-testable in isolation, no real routing needed).
- API client: envelope-unwrapping logic, error-mapping.
- Layout/Sidebar: renders the correct nav items for a given role (data-driven from the `panel_modules.md` table above, not hardcoded per-test).

**No integration/E2E tests this sprint** (e.g. Playwright/Cypress) — same honest "not this sprint" scope discipline as the backend's own "0 integration tests" status across all 12 sprints, for the same underlying reason (no live environment to run them against here).

## 12. Sprint 13 Scope — Foundation, explicitly bounded

To avoid the exact failure mode this whole project has repeatedly guarded against (scope creep, parallel implementations, unapproved product decisions), Sprint 13 is proposed as:

**In scope:**
- Vite + React + TypeScript + Tailwind + shadcn/ui project setup (`package.json`, `vite.config.ts`, `tsconfig.json` — currently all empty).
- API client (Section 5) + token refresh (Section 6), for the `auth` module only.
- Login, Register, Verify pages (Section 4) — fully functional against the real backend.
- Four layouts (Section 7) + role-based routing guard (Section 3).
- Sidebars (Section 8) — navigation shell only, linking to placeholder pages.
- Dashboard shell (Section 9) — empty/loading states, no real widgets.
- Test suite (Section 11) for everything above.

**Explicitly NOT in scope** (future sprints, same as every backend module's "Future Improvements"):
- Any feature page's real functionality (Users CRUD table, Test-taking screen, Results charts, etc.) — each of those is realistically its own sprint, matching how backend features (`tests`, `questions`, `attempts`) were each separate sprints.
- The test-taking screen (`ui_ux_blueprint.md` §4.3) specifically — it's the most complex UI in the platform (timer, auto-save, question navigator) and deserves its own dedicated sprint, not a Foundation-sprint afterthought.
- E2E tests.
- `httpOnly` cookie migration (Outstanding Decision #5) — would need backend changes, out of a frontend-only sprint by definition.

---

## Outstanding Decisions — must be resolved before implementation

1. **State management**: TanStack Query (server state) + Zustand (client state) — approved as the standard, or a different pairing preferred (Redux Toolkit, plain Context)?
2. **Type source**: hand-written TypeScript interfaces mirroring backend `*Out` schemas this sprint, versus investing in OpenAPI codegen now (which would be more valuable once the backend's `response_model=` gap is eventually closed)?
3. **`debug_code` in the register response** — confirmed as a known, pre-existing backend limitation (not something Sprint 13 fixes), just needs your acknowledgment that the frontend will consume it as-is for now.
4. **HTTP client**: `axios` (richer interceptor API, slightly heavier) vs. native `fetch` wrapped manually (zero dependency, more code to write for interceptors)?
5. **Token storage**: `localStorage` (simple, XSS-exposed, default if nothing else is chosen) vs. deferring to a future sprint that also touches the backend to support `httpOnly` cookies?
6. **Confirm the exact current role list** to branch UI on — should be read directly from the seeded `roles` table rather than assumed; needs a quick DB/seed-script check before routing logic is written.
7. **Confirm Sprint 13's bounded scope** (Section 12) — Foundation only, no feature pages — versus a larger first frontend sprint that includes at least one working feature (e.g. the Dashboard's real widgets, or a first CRUD page) to have something demonstrably "real" sooner.
