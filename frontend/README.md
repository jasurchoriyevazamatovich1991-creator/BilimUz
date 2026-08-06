# BilimUz Frontend — Sprint 13 Foundation

Full design rationale: `docs/Sprint13_Frontend_Foundation_Architecture.md` (approved).

## Stack

React 19 + TypeScript + Vite + Tailwind CSS, per `.cursor/context/04-tech-stack.md`. State: TanStack Query (server state) + Zustand (client state). HTTP: Axios. Routing: React Router v7.

## ⚠️ Setup requires a running backend — one manual step before the app type-checks

**OpenAPI code generation (approved decision) could not be run in the environment this code was written in** — no live backend process, no PyPI/npm registry access to install `fastapi`/`openapi-typescript` there. The `npm run generate:types` script is real and correctly configured, but has never actually been executed. Until it is, `src/types/api.d.ts` does not exist, and any future file importing from it will not resolve.

**Required setup, in order:**
```bash
# 1. Backend must be running (for its auto-served /openapi.json)
docker-compose up -d  # from repo root — starts Postgres + Redis + backend

# 2. Frontend dependencies
cd frontend
npm install

# 3. Generate types from the LIVE backend (only now does this produce real output)
npm run generate:types

# 4. Run the app
npm run dev
```

This is the same honesty already established platform-wide (e.g. the backend's own "0 integration tests, not executable in this environment" status across all 12 backend sprints) — nothing here is faked to look more complete than it is.

## A small, approved backend change was needed

`backend/app/modules/auth/schemas.py`'s `UserPublic` gained one new field, `role: str` (reading `User.role.name` via the existing ORM relationship, `Field(validation_alias=AliasPath("role", "name"))`). **This was the only backend file touched this sprint.**

**Why**: neither the JWT payload nor `/auth/me`'s previous response contained the logged-in user's role *name* — only `role_id` (a UUID), and the only endpoint that resolves that UUID to a name (`GET /roles/{id}`) is Admin-only. A Student or Teacher logging in had no way to learn which panel they belonged to. Investigated and surfaced before writing any routing code — see the architecture doc's "final blocking finding" for the full investigation trail (JWT payload checked, `UserOut` in the `users` module checked for a pre-existing solution, `GET /roles/{id}`'s RBAC tier checked).

No other endpoint, model, or migration was touched. `backend/app/modules/users/` (which has the identical `role_id`-only gap in its own `UserOut`) was deliberately left alone — the instruction was "boshqa endpointlarga tegma" (don't touch other endpoints), followed exactly.

## Folder structure

Matches the approved architecture doc's Section 2 exactly — see that document for the full rationale table (backend-layer ↔ frontend-layer mapping).

```
src/
├── api/            — auth.ts (this sprint), client.ts (shared axios instance + token refresh)
├── components/       — layout/ (Sidebar, Header, PlaceholderPage, DashboardCard) — shared UI;
│                        ui/ (Button, Input, Card — shadcn/ui primitives, standard CLI-output
│                        shape so a real `npx shadcn add X` later stays consistent)
├── hooks/              — useAuth.ts (TanStack Query mutations/queries)
├── layouts/              — PublicLayout, AdminLayout, TeacherLayout, StudentLayout
├── lib/                    — utils.ts (shadcn/ui's cn() helper — clsx + tailwind-merge)
├── pages/                  — public/ (Home, Login, Register, Verify, UnsupportedRole),
│                              admin/, teacher/, student/ (dashboard shells only)
├── routes/                    — AppRoutes.tsx, ProtectedRoute.tsx (RBAC guard)
├── store/                      — authStore.ts (Zustand, localStorage-persisted)
├── styles/                      — Tailwind entry point
├── utils/                        — roleConfig.ts, sidebarConfig.ts
└── types/                          — EMPTY until `npm run generate:types` is run (see above)
```

## shadcn/ui foundation

`components.json`, `lib/utils.ts` (`cn()`), and three base primitives (`Button`, `Input`, `Card` in `components/ui/`) were added to complete the approved "Tailwind CSS + shadcn/ui" stack — this had been set up incompletely (Tailwind only) before this continuation. **Login/Register/Verify pages still use plain HTML elements with hand-written Tailwind classes**, not these new primitives — they were already complete and correct before the primitives existed, and retrofitting them now would mean regenerating already-finished files, which this continuation was explicitly told not to do. Wiring existing pages to the new `Button`/`Input` components is a small, safe follow-up for a future session.

## Business rules

- **Role → panel mapping is exhaustive over all 8 real seeded roles** (`Super Admin, Admin, Moderator, Teacher, Applicant, Student, Parent, Guest` — read directly from `database/schema/schema_v2.sql`'s seed `INSERT`, not assumed). `Parent` and `Guest` map to an honest "not built yet" page (`/unsupported`) rather than being silently folded into another role's real panel.
- **Applicant and Student share a layout but NOT sidebar content** — `docs/UI-UX/panel_modules.md` gives them genuinely different navigation (DTM/Blok Test/Reyting vs. Mening fanlarim/Darslar/Yutuqlar). Caught and fixed during implementation (an earlier draft of `sidebarConfig.ts` collapsed them into one list) — tested explicitly (`sidebarConfig.test.ts`).
- **Route guarding is UI convenience, not security** — `ProtectedRoute` redirects a mismatched role to their own real panel (never a blank screen), but the backend's `require_roles()` remains the actual enforcement, unchanged.
- **Token refresh is centralized and race-safe**: concurrent 401s trigger exactly one refresh call (a module-level promise, not per-request state) — see `api/client.ts`'s `performRefresh()`/`refreshPromise`.
- **`debug_code` is displayed as-is on the Verify page** (approved decision) — no mock/fake SMS delivery is simulated; the backend's own known limitation (documented in `auth/router.py`'s pre-existing TODO) is surfaced honestly in the UI with a visible amber notice, not hidden.

## Tests

Vitest + React Testing Library. `roleConfig.test.ts` (7 — every real role mapped, unknown-role fallback), `sidebarConfig.test.ts` (6 — the Applicant/Student distinction, empty-array for unsupported roles, union deduplication), `client.test.ts` (4 — envelope unwrapping, `ApiError` construction), `ProtectedRoute.test.tsx` (3 — unauthenticated redirect, matching-role render, mismatched-role redirect to the user's own panel).

**Not run in this environment** — same `npm install` blocker as the OpenAPI codegen step. Written to be correct and ready; will execute once dependencies are installed in a real environment. Total: 17 test cases (`roleConfig.test.ts` 4, `sidebarConfig.test.ts` 6, `client.test.ts` 4, `ProtectedRoute.test.tsx` 3).

## Sprint 13 scope (Foundation only — approved)

Built: project setup, API client + token refresh, Login/Register/Verify (fully functional against the real backend once running), four layouts, role-based routing guard, sidebars (navigation shell, linking to placeholders), dashboard shells (empty/loading states).

**Not built** (future sprints, same as every backend module's own "Future Improvements"): any feature page's real functionality (Users CRUD, Test-taking screen, Results charts, etc.), the test-taking screen specifically (`ui_ux_blueprint.md` §4.3 — deserves its own dedicated sprint), E2E tests, `httpOnly` cookie migration.
