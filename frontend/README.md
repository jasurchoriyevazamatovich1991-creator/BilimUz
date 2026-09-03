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

## Sprint 20 — Student Test Taking / Attempt UI

**First genuinely Student-facing feature build** — every prior sprint (15–19) was Admin-panel only. Follows the pre-implementation audit's Outstanding Decisions (all 5 approved) exactly.

- **A real BACKEND GAP found during implementation, not caught in the audit**: `SaveAnswerRequest.selected_option` is a single UUID, not a list — even for `multiple_choice` questions, only ONE option can be saved as the answer via the real endpoint. `AttemptPage.tsx` therefore renders single-select (radio) behavior for every question regardless of `question_type` — not a frontend limitation, a real backend one, documented in code rather than papered over with invented multi-select answer-saving.
- **`api/attempts.ts` extended** (Sprint 14's `myCount()` untouched) with the full lifecycle: `listMine`, `start`, `get`, `saveAnswer`, `submit`, `getResult` — every path verified directly against the router (`POST /attempts/start`, `GET /attempts/me`, `GET /attempts/{id}`, `PATCH /attempts/{id}/answer`, `POST /attempts/{id}/submit`, `GET /attempts/{id}/result`). **`api/results.ts` extended** with `create`/`get`.
- **New `hooks/useAttempt.ts`**: `useActiveAttemptForTest` (approved decision 3 — checks `GET /attempts/me?test_id=&status=in_progress` before ever calling `start()`), `useStartAttempt`, `useAttempt` (full state, refetches on mount — the refresh-recovery mechanism, approved decision 4), `useSaveAnswer` (patches the cached attempt via `setQueryData`, not a full refetch per click), and `useSubmitAndCreateResult` — the composed mutation for approved decision 1: calls `submit()` then `results.create()` only on success, tags a distinct `stage: "createResult"` error so a post-submit failure never implies the submission itself needs redoing.
- **New `hooks/useResults.ts`** (no prior file existed): `useResult` (detail) + `useCreateResultForFinishedAttempt` (the idempotent create-or-get, used only when a student lands on an already-finished attempt without having gone through this session's submit flow).
- **New `components/attempts/Timer.tsx`** (approved decision 2): purely visual, computed fresh from `expiresAt` every render/tick, **zero `localStorage` use** (tested explicitly via a `Storage.prototype` spy), calls `onExpire` via a ref guard so it can never double-fire. Matches `ui_ux_blueprint.md`'s documented 5-minute red-warning behavior (verified in the doc before implementing, not assumed).
- **New `components/attempts/QuestionNavigator.tsx`**: matches the documented UX (answered/current/unanswered coloring) exactly — no flag/bookmark state built, since no backend field supports it.
- **Race-condition guard** (approved decision 2): both the manual Submit button and the Timer's `onExpire` call the *same* `fireSubmit()` function in `AttemptPage.tsx`, guarded by both `submitAndCreateResult.isPending` and a synchronous `useRef` flag — cannot double-fire even if both trigger in the same tick.
- **Four new Student pages**: `TestsListPage.tsx` (published-only), `TestDetailPage.tsx` (Start/Continue gating, tested explicitly that `start()` is never called when an active attempt exists), `AttemptPage.tsx` (the core screen), `ResultPage.tsx` (shows only real `ResultOut` fields — no invented per-question breakdown, since that endpoint doesn't exist).
- **Certificates: nothing built** (approved decision 5) — no UI, no API, no route.
- `ConfirmDialog`, `ErrorState`, `Button`/`Input`/`Card`, `useDebouncedValue`, `useTest`/`useTestsList` (Sprint 19), `ProtectedRoute`, `StudentLayout` all reused unchanged.
- 15 new tests: `Timer.test.tsx` (5 — including the explicit no-localStorage and single-fire guarantees), `useAttempt.test.tsx` (6 — the critical submit-before-createResult ordering, createResult never called if submit fails, distinct error tagging, active-attempt query shape), `TestDetailPage.test.tsx` (4 — Continue vs. Boshlash gating, `start()` never called when active). **Total: 110.**

## Sprint 19 — Tests & Questions UI

**The most complex sprint so far.** Two requested-analysis assumptions corrected before any code was written:

- **"Test ↔ Lesson" does not exist** — Tests relate to Subject/Grade/Topic only (all optional, all remain editable post-creation, unlike every prior module's immutable-parent shape). No `lesson_id` field anywhere.
- **No "Archive" action for Tests** — `ALLOWED_STATUS_TRANSITIONS` mentions an `archived` state in the backend's own constants, but only `POST /{id}/publish` exists as a real endpoint. No Archive button built.
- **Question Media is a plain URL field**, not a file-upload flow — no integration with the `uploads` module, same shape as Lessons' `video`/`pdf`.

Sprint 19 additions:
- **Tests**: `api/tests.ts` extended (Sprint 14's `publishedCount()` untouched), `hooks/useTests.ts` (new), `pages/admin/TestsListPage.tsx` + `TestFormPage.tsx`. A **Publish button** shown only when `status === "draft"` and `question_count > 0` — matches the backend's own precondition exactly, tested explicitly (draft+0-questions, draft+N-questions, already-published — three distinct gating states).
- **Questions — nested under a Test** (`/admin/tests/:testId/questions`, approved decision 4, no standalone sidebar entry): `api/questions.ts` (new, 10 real endpoints — 5 Question + 3 Option + 2 Media), `hooks/useQuestions.ts`, `pages/admin/TestQuestionsListPage.tsx` + `QuestionFormPage.tsx` — the most complex form in the project.
- **Options editor**: all edits (add/remove/edit-text/toggle-correct) accumulate in **local component state only**. On Create, submitted nested with the single `POST /questions` call. On Edit, a diff against the originally-loaded snapshot is computed on Submit and executed via the real granular `add/update/delete` option endpoints — one call per actual change, never per keystroke (approved decision 6).
- **Conditional validation** (approved decision 7, submit-time, never a disabled button): `single_choice`/`true_false` require exactly 1 correct option; `multiple_choice` requires at least 1; both require ≥2 options total — mirrors the backend's own `validate_option_set` message text exactly. `essay`/`short_answer` show no options section at all.
- **Radio-vs-checkbox behavior**: `single_choice`/`true_false` use native radio semantics (selecting one deselects any other), `multiple_choice` uses independent checkboxes — tested explicitly.
- **New `components/questions/MediaTypeBadges.tsx`** (approved decision 5) — deliberately NOT a modification of Sprint 18's `ContentBadges.tsx` (different, larger type set: `image/audio/video/formula`).
- **Cache isolation** (approved decision 8, verified directly — no code reference, only explanatory comments): Option/Media mutations invalidate only `["questions", ...]`, never `["tests", ...]`.
- `ConfirmDialog`, `StatusBadge`, `useDebouncedValue`, `useSubjectsList`/`useGradesList`/`useTopicsList` (read-only, for Tests' pickers) all reused unchanged.
- 15 new tests: `MediaTypeBadges.test.tsx` (4), `TestFormPage.test.tsx` (4 — no Archive button ever, three-state Publish gating), `QuestionFormPage.test.tsx` (7 — the critical conditional validation, submit never blocked, radio-deselect behavior, essay hides options entirely). **Total: 95.**

## Sprint 18 — Lessons UI

**Key finding, investigated before writing code**: `LessonCreateRequest`/`LessonUpdateRequest` have a real backend `model_validator` requiring **at least one of `video`, `pdf`, `content`** — no prior CRUD sprint's form had this "at least one of several optional fields" shape.

- **`api/lessons.ts` extended** (Sprint 14's `count()` untouched), following `api/topics.ts`'s exact CRUD style. New `hooks/useLessons.ts` mirrors `hooks/useTopics.ts` — same cache-isolation discipline (Lessons' mutations never touch `["topics", ...]`, verified directly; reading Topics for the picker never invalidates Lessons' cache either).
- **RBAC matches Topics, not Subjects/Grades** (approved, verified against `require_roles("Admin", "Super Admin", "Teacher")`): Teacher has real write access here — tested explicitly (`LessonsListPage.test.tsx`), the same class of risk Sprint 17 flagged for Topics.
- **New, small, reusable-shaped component**: `components/lessons/ContentBadges.tsx` — Video/PDF/Text pills, only rendered for fields actually present, matching `StatusBadge`'s pill visual style (no new icon library).
- **`video`/`pdf` use native `<input type="url">`** (approved decision 2) — zero new library, browser-native validation.
- **"At least one of video/pdf/content" — submit is never disabled** (approved decision 3): checked in `handleSubmit`, a single clear message (`"Video, PDF yoki matndan kamida bittasini kiriting."`) renders when all three are empty, and the mutation is never called — no malformed request reaches the backend. Tested explicitly, including that the submit button stays enabled.
- **`topic_id` is set-once**: plain read-only text in edit mode (approved decision 4, same pattern as Grades' `name` and Topics' `subject_id`), never a disabled `<select>`. Tested explicitly.
- `ConfirmDialog`, `StatusBadge`, `useDebouncedValue`, and `hooks/useTopics.ts` (read-only, for the picker/lookup) all reused unchanged. No new sidebar entry needed (`Darslar` already existed from Sprint 13). `routes/AppRoutes.tsx` extended via the existing `excludePaths` mechanism.
- 11 new tests: `ContentBadges.test.tsx` (3), `LessonsListPage.test.tsx` (4 — the critical Teacher-write-access test, plus Student read-only), `LessonFormPage.test.tsx` (4 — topic read-only text, the cross-field validation message with submit never blocked, successful submit with one field filled, `type="url"` confirmed). **Total: 80.**

## Sprint 17 — Subjects, Grades & Topics UI

**Key finding, investigated before writing code**: Topics has a **wider write RBAC tier** than Subjects/Grades — `Admin, Super Admin, Teacher` vs. `Admin, Super Admin` only (verified against real `require_roles(...)` calls in all three backend routers). Each page computes its own `canWrite` against its own module's real role list — never copy-pasted blindly across the three.

- **`api/subjects.ts` extended** (Sprint 14's `count()` untouched); **`api/grades.ts` and `api/topics.ts` are new files**, same style/architecture as `api/subjects.ts` (approved decision — confirmed directly that neither existed before writing).
- **Subjects' `color` field**: native HTML5 `<input type="color">` (approved — no new UI library), always yields lowercase `#RRGGBB`, matching the backend's hex validation exactly. Default value `#0c447c` — the platform's own documented brand primary (`tailwind.config.js`), not an arbitrary placeholder.
- **Grades' Edit form**: `name` renders as **plain read-only text**, never a disabled input (approved decision 4) — matches `GradeUpdateRequest`'s real backend shape (no `name` field at all). Tested explicitly (`GradeFormPage.test.tsx`) that no `textbox` role exists for the name.
- **Topics — the first cross-module admin CRUD page**: Subject/Grade dropdowns (both the Create form's pickers and the List page's filters) read `api/subjects.ts`/`api/grades.ts` read-only, mirroring the backend's own one-directional `topics → subjects/grades` dependency at the UI layer for the first time. `subject_id` is set-once (no field for it in edit mode, matching the backend exactly); `grade_id` remains editable.
- **"N ta mavzu" indicator**: not built (approved decision — no new aggregation endpoint, no frontend-computed count).
- **Topics' cache is fully isolated** (approved decision 5) — `hooks/useSubjects.ts`/`useGrades.ts` never reference the `"topics"` query key, `hooks/useTopics.ts` never references `"subjects"`/`"grades"` — verified directly, not just by convention.
- `ConfirmDialog`, `StatusBadge` (all three modules' `active/inactive/archived` render correctly through the existing fallback path, no changes needed), `useDebouncedValue` all reused unchanged, third/fourth real consumers.
- `routes/AppRoutes.tsx` extended using the existing `excludePaths` mechanism (Sprint 15/16) — no new routing infrastructure. No new sidebar entries needed (all three already existed from Sprint 13's original scaffold).
- 9 new tests: `SubjectsListPage.test.tsx` (2 — Teacher is read-only here), `TopicsListPage.test.tsx` (4 — **the critical test**: Teacher genuinely sees write controls on Topics, Moderator does not, plus the read-only Subject-name-resolution check), `GradeFormPage.test.tsx` (3 — name is real read-only text, not a disabled input). **Total: 69.**

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
