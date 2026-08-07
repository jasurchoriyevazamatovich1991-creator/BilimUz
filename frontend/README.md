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

## Sprint 16 — Schools & Learning Centers UI (full CRUD)

**Key finding, investigated before writing code**: unlike Sprint 15's Users module, Schools and Learning Centers have **full CRUD on the backend** (`GET/GET/POST/PATCH/DELETE`, all verified) — so unlike Users, this sprint legitimately ships Create, Edit, **and** Delete.

- **Two independent pages per module** (approved decision — not one generic mega-component): `SchoolsListPage.tsx` + `SchoolFormPage.tsx` (shared Create/Edit), `LearningCentersListPage.tsx` + `LearningCenterFormPage.tsx`. Deliberately duplicated structure, not abstracted, matching the backend's own Sprint 10 precedent of keeping structurally-similar modules independent.
- **New, reusable**: `components/common/ConfirmDialog.tsx` (approved for reuse in future Delete flows across other modules), `utils/deriveOptions.ts` (`deriveDistinctValues` — Region filter dropdown built from the currently-loaded page of results, no new backend endpoint, approved decision).
- **`api/schools.ts` and `api/learningCenters.ts` extended** (Sprint 14's `count()` on each untouched) with `list/get/create/update/remove`. New `hooks/useSchools.ts` + `hooks/useLearningCenters.ts` mirror `hooks/useUsers.ts`'s pattern exactly (toast-via-`useEffect`, broad list-key cache invalidation on mutation).
- **`StatusBadge` reused directly, unchanged** — Schools/Learning Centers' 3-value status enum (`active/inactive/archived`) renders correctly through the same component built for Users' 4-value enum in Sprint 15, no Users-specific logic inside it to work around.
- **Moderator write-gating, found and fixed during implementation**: an early draft only hid the "Qo'shish" button and redirected Moderator away from `/admin/schools/:id` entirely — but the backend's `GET /schools/{id}` is public, so a Moderator reading school details is a permitted action. Fixed to redirect away only from the Create route (`/admin/schools/new`, genuinely off-limits), while the edit route renders a real read-only view (every field `disabled`, zero Save/Delete buttons) for non-writers instead of denying access outright.
- **Sidebar**: `utils/sidebarConfig.ts`'s `ADMIN_ITEMS` gained two entries (`Maktablar` → `/admin/schools`, `O'quv markazlari` → `/admin/learning-centers`), inserted right after `Foydalanuvchilar` per the approved order.
- **`routes/AppRoutes.tsx` minimally extended**: `placeholderRoutesFor()`'s existing `excludePaths` parameter (added in Sprint 15) now also excludes both new paths — no new routing mechanism needed.
- 13 new tests: `deriveOptions.test.ts` (3), `ConfirmDialog.test.tsx` (7), `SchoolsListPage.test.tsx` (3 — the critical Moderator-vs-Admin write-control visibility guarantee). **Total: 60.**

## Sprint 15 — Users Management UI (List/View/Edit only)

**Critical finding, investigated before writing code**: the backend Users module has no `POST /users` and no `DELETE /users/{id}` — only 6 GET/PATCH endpoints exist (verified exhaustively). "CRUD" was requested but Create/Delete don't exist. **Approved decision (Option A)**: this sprint ships List, View, Edit, Search, Filter, Pagination only — no Create button, no Delete button, no disabled/hidden placeholders for either, anywhere.

- **New, reused-where-possible**: `api/roles.ts` + `hooks/useRoles.ts` (role_id → name lookup, deliberately NOT an extension of the unrelated `utils/roleConfig.ts`, which maps role *name* → panel). `hooks/useDebouncedValue.ts` (no external library, approved). `hooks/useUsers.ts` (list/get/update/changeRole, same toast-via-`useEffect` pattern as `useDashboardStats.ts`). `components/users/StatusBadge.tsx` — **display-only**, renders all 4 real backend status values (`active, inactive, banned, pending_verification` — verified against `users/models.py`'s enum) including `banned`, with zero ban/unban action anywhere (approved decision 5).
- **`api/users.ts` extended, not replaced** — Sprint 14's `count()` untouched, `list/get/update/changeRole` added.
- **shadcn/ui primitives get their first real use**: `Button`, `Input`, `Card` (built in Sprint 13's continuation, never consumed until now).
- **`routes/AppRoutes.tsx` minimally extended** (not rewritten): `/admin/users` and `/admin/users/:userId` now render real pages instead of `PlaceholderPage` — `placeholderRoutesFor()` gained an `excludePaths` parameter so the sidebar entry itself (`utils/sidebarConfig.ts`, unchanged) doesn't need touching.
- **Role-change is Super-Admin-gated in the UI too**, not just relying on the backend's 403 — matches the backend's own documented "never bundle privilege escalation with an ordinary edit" design intent.
- 14 new tests: `useDebouncedValue.test.ts` (4), `StatusBadge.test.tsx` (6 — 4 via `it.each` over every real status value, + 2 more: unknown-status fallback, explicit "no ban/unban button" guarantee), `UsersListPage.test.tsx` (4, including the explicit "no Create/Delete button anywhere" guarantee — the single most important behavioral test this sprint). **Frontend total: 47.**

## Sprint 14 — Header menu, ErrorBoundary, Dashboard integration

Built on top of Sprint 13 without rewriting its protected pieces (Login, Refresh, Logout, Auth Guard, Sidebar generation, Routing — all untouched):

- **Header dropdown** (`components/layout/Header.tsx`, rewritten as approved): avatar initials, name, role badge, Profil + Chiqish menu items. Click-outside and `Escape` both close it. Profile links to `${panel}/profile`, which resolves via the *existing* `placeholderRoutesFor()` mechanism in `AppRoutes.tsx` (untouched) — Admin's sidebar gained one new `Profil` entry (`utils/sidebarConfig.ts`) since Teacher/Student already had one; this was the only change needed to make the link resolve to a real route.
- **Global `ErrorBoundary`** (`components/ErrorBoundary.tsx`): one app-wide boundary (approved decision, not per-layout), wraps `<AppRoutes/>` in `App.tsx`. Catches render crashes, shows a real fallback instead of a blank screen.
- **Toast system** (`store/toastStore.ts` + `components/layout/ToastContainer.tsx`): global, non-persisted Zustand store, auto-dismiss after 5s. **Deliberately not wired into `api/client.ts`'s interceptor** — that would double-surface form errors (already shown as banners per Sprint 13's documented UX) as toasts too. Toast triggering lives entirely in the new `hooks/useDashboardStats.ts`, via `useEffect` (not directly in render — an earlier draft called the toast action during render, which would have re-fired on every render while `isError` stayed true; fixed before considered complete).
- **Dashboard backend integration** (`api/users.ts`, `tests.ts`, `subjects.ts`, `results.ts`, `attempts.ts`, `ai.ts`, `schools.ts`, `learningCenters.ts`, `lessons.ts`, `certificates.ts`, `payments.ts` + `hooks/useDashboardStats.ts`): every widget verified against backend source before writing. Widget set per the approved list — **Super Admin**: Users, Schools, Learning Centers, Subjects, Tests, Payments, Results. **Teacher**: Subjects, Lessons, Tests, Results. **Student/Applicant**: Assigned Tests, Results, Certificates.
  - **Two real gaps found and handled honestly, not faked**: (1) no admin-wide `payments`/`results` list endpoint exists (only `/me`-scoped or catalog-only) — the "Payments" widget shows the real, public `/payments/plans` catalog count instead (clearly labeled "To'lov rejalari", not implying transaction volume), while "Natijalar" (Super Admin) has no real substitute and renders a new `<UnavailableState/>` component instead of fake data. (2) No "assignment" concept exists anywhere in the backend schema — Student's "Assigned Tests" widget shows the same published-tests catalog everyone sees, labeled "Mavjud testlar" (Available), not "Biriktirilgan" (Assigned).
  - Each widget shows inline `<ErrorState/>` on failure AND triggers the existing global toast — both, not either/or (approved decision, existing toast system reused, no new one built).
- **Header additions**: Settings menu item added alongside Profile/Logout. Required extending `utils/sidebarConfig.ts` with a `Sozlamalar` entry for Teacher/Applicant/Student (Admin already had one) and a `Profil` entry for Admin (Teacher/Student already had one) — small, justified additions so both links resolve via the *existing, untouched* `placeholderRoutesFor()` route-generation mechanism in `AppRoutes.tsx`. No new backend functionality, no new routing code.

## Business rules (Sprint 13, still accurate)

- **Role → panel mapping is exhaustive over all 8 real seeded roles** (`Super Admin, Admin, Moderator, Teacher, Applicant, Student, Parent, Guest` — read directly from `database/schema/schema_v2.sql`'s seed `INSERT`, not assumed). `Parent` and `Guest` map to an honest "not built yet" page (`/unsupported`) rather than being silently folded into another role's real panel.
- **Applicant and Student share a layout but NOT sidebar content** — `docs/UI-UX/panel_modules.md` gives them genuinely different navigation (DTM/Blok Test/Reyting vs. Mening fanlarim/Darslar/Yutuqlar). Caught and fixed during implementation (an earlier draft of `sidebarConfig.ts` collapsed them into one list) — tested explicitly (`sidebarConfig.test.ts`).
- **Route guarding is UI convenience, not security** — `ProtectedRoute` redirects a mismatched role to their own real panel (never a blank screen), but the backend's `require_roles()` remains the actual enforcement, unchanged.
- **Token refresh is centralized and race-safe**: concurrent 401s trigger exactly one refresh call (a module-level promise, not per-request state) — see `api/client.ts`'s `performRefresh()`/`refreshPromise`.
- **`debug_code` is displayed as-is on the Verify page** (approved decision) — no mock/fake SMS delivery is simulated; the backend's own known limitation (documented in `auth/router.py`'s pre-existing TODO) is surfaced honestly in the UI with a visible amber notice, not hidden.

## Tests

Vitest + React Testing Library. Sprint 13 (17): `roleConfig.test.ts` (4), `sidebarConfig.test.ts` (6), `client.test.ts` (4), `ProtectedRoute.test.tsx` (3). Sprint 14 (16 new): `toastStore.test.ts` (4), `ErrorBoundary.test.tsx` (2), `Header.test.tsx` (6), `sidebarConfig.test.ts` additions (4 — Settings/Profil entries across roles). **Total: 33.**

**Not run in this environment** — same `npm install` blocker as Sprint 13.

## Sprint 13 scope (Foundation only — approved)

Built: project setup, API client + token refresh, Login/Register/Verify (fully functional against the real backend once running), four layouts, role-based routing guard, sidebars (navigation shell, linking to placeholders), dashboard shells (empty/loading states).

**Not built** (future sprints, same as every backend module's own "Future Improvements"): any feature page's real functionality (Users CRUD, Test-taking screen, Results charts, etc.), the test-taking screen specifically (`ui_ux_blueprint.md` §4.3 — deserves its own dedicated sprint), E2E tests, `httpOnly` cookie migration.
