# Sprint 17 — Subjects, Grades & Topics UI: Architecture Impact Analysis

**Status: DESIGN ONLY — no code written, no repository files modified, no ZIP.**

## Key findings, established before any design choice below

**1. Three modules, three different RBAC tiers for writes** — not uniform, verified exhaustively:

| Module | Write auth (Create/Update/Delete) |
|---|---|
| Subjects | Admin, Super Admin |
| Grades | Admin, Super Admin |
| **Topics** | **Admin, Super Admin, Teacher** |

Topics allows Teacher to write, Subjects/Grades do not. Copy-pasting Sprint 16's `canWrite = role === "Admin" || role === "Super Admin"` gating onto Topics without adjustment would incorrectly hide Teacher's real write access — a real bug this analysis exists to prevent before it's written.

**2. Grades has no name-update capability** — `GradeUpdateRequest` only accepts `status`, deliberately (docstring: "renaming in place could silently break anything referencing the old name elsewhere," same reasoning already applied to `roles`/`subjects` in the backend). Grades' Edit form is therefore structurally different from Subjects/Topics: **status-only**, `name` shown read-only after creation, not a smaller version of the same form.

**3. Grades has no `icon`/`color` fields** — Subjects does (`icon`, `color` with hex validation). Not a smaller Subjects form; a genuinely different field set.

**4. All three already have real sidebar entries and placeholder routes** (`Fanlar → /admin/subjects`, `Sinflar → /admin/grades`, `Mavzular → /admin/topics`, from Sprint 13's original scaffold) — **unlike Sprint 16's Schools/Learning Centers, no new sidebar entries are needed**, this sprint follows Sprint 15's pattern (swap `PlaceholderPage` for a real page via `AppRoutes.tsx`'s existing `excludePaths` mechanism), not Sprint 16's pattern (add new `ADMIN_ITEMS` rows).

**5. Topics has a real parent-child relationship to both Subjects and Grades** — `TopicCreateRequest.subject_id` is **required** (a Topic cannot exist without a Subject), `grade_id` is **optional**. Neither can be changed to a *different* subject after creation (`TopicUpdateRequest` has no `subject_id` field at all — only `grade_id` is mutable post-creation). The Topics form therefore needs **two dropdowns sourced from other modules' data** (Subjects list, Grades list) — the first cross-module data dependency in any admin CRUD page so far (Sprint 15/16 pages were each self-contained).

---

## 1–3. Existing Backend Modules (full shape, confirmed above)

All three have full CRUD (`GET/GET/POST/PATCH/DELETE`), same shape as Sprint 16's Schools/Learning Centers, not Sprint 15's read-only-for-writes Users. `SubjectOut`: `id, name, icon, color, status, created_at, updated_at`. `GradeOut`: `id, name, status, created_at, updated_at` (smallest of the three — no descriptive fields at all beyond name). `TopicOut`: `id, subject_id, grade_id, title, description, order_number, status, created_at, updated_at`.

## 4. Existing Frontend Architecture (Sprints 13–16) — what Sprint 17 builds on

Everything needed already exists: `api/client.ts`, `ProtectedRoute`, `AdminLayout`, `types/pagination.ts`, `components/common/ConfirmDialog.tsx` (Sprint 16, approved for exactly this kind of reuse), `components/users/StatusBadge.tsx` (reused unchanged a third time — Subjects/Grades/Topics' status enums need checking against its existing `STATUS_STYLES` map, see Risks), `hooks/useDebouncedValue.ts`, `utils/deriveOptions.ts` (Sprint 16 — not obviously needed here since none of these three have a free-text geographic field like Region, but worth checking per-module), `hooks/useRoles.ts` (not applicable — none of these three modules have a role concept, correctly excluded, same as Sprint 16).

**No existing `api/subjects.ts`, `api/grades.ts`, or `api/topics.ts` files exist yet** — unlike Schools/Learning Centers/Users (which all had a Sprint 14 dashboard-widget-driven `count()`-only starter file to extend), Subjects was the one exception: Sprint 14's dashboard widget for Subjects used `api/subjects.ts`'s `count()` — **this file already exists** (verified — built in Sprint 14). Grades and Topics have **no api file at all yet** (their Sprint 14 dashboard widgets, if any, would need checking — Teacher's dashboard used `lessonsApi`/`testsApi`, not grades/topics directly). This needs a direct check before implementation (see Outstanding Decisions).

## 5. Existing Reusable CRUD Patterns (Sprint 15/16 precedent, to be followed a third time)

The established shape: `api/{module}.ts` (list/get/create/update/remove, extending any existing partial file), `hooks/use{Module}.ts` (TanStack Query, toast-via-`useEffect`, broad list-key invalidation), `pages/admin/{Module}ListPage.tsx` (table, search, filters, pagination, role-gated write controls), `pages/admin/{Module}FormPage.tsx` (shared Create/Edit, read-only rendering for non-writers per Sprint 16's fix). Three more modules, same shape — **not** abstracted into one generic component (Sprint 16's explicit precedent: structurally-similar-but-independent modules stay independent, matching the backend's own module boundaries).

## 6–8. Subjects / Grades / Topics UI Architecture

- **Subjects**: closest to Sprint 16's Schools in shape (name + a couple of optional descriptive fields + status). New field type: `color` (hex) — needs either a plain text input (simplest, matches the backend's own plain-string validation) or a color picker (nicer, not existing anywhere in the app yet) — a real, small UI choice (see Outstanding Decisions).
- **Grades**: the simplest of the three — List, View, status-only Edit (no name field in the edit form, per Finding #2), Create (name only), Delete. Closer in spirit to Sprint 15's Users (partial-edit) than Sprint 16's full-field-edit Schools, despite having full CRUD.
- **Topics**: the most complex — Create/Edit form needs a Subject dropdown (required) and a Grade dropdown (optional), both populated from **other modules' list endpoints**, read-only for this purpose (same one-directional dependency shape the backend itself uses — `topics` reading `subjects`/`grades` read-only, mirrored here at the UI layer for the first time).

## 9. Parent-Child Relationships (Subjects → Topics, Grades → Topics)

Two distinct implications:
- **Topics' own form** needs Subject/Grade *pickers* (dropdowns sourced from `api/subjects.ts`'s `list()` and a new `api/grades.ts`'s `list()`), not full CRUD access to those modules from within the Topics page.
- **Subjects' and Grades' list/detail pages could show topic counts or links** ("N ta mavzu") — a nice-to-have, not required by the approved Sprint 16 pattern for Schools (which had no child relationship to display) and not assumed here without confirmation (see Outstanding Decisions) — would need one more read call per row/detail (`GET /topics?subject_id=X`), real and available, but adds scope.

## 10. Search, Filtering, Pagination

`types/pagination.ts`'s `PaginatedResponse<T>` reused directly for all three (verified — all three `ListParams`/response shapes match exactly, same as every prior CRUD sprint). Filters: Subjects (search, status), Grades (search, status — no other filterable fields exist), Topics (search, `subject_id`, `grade_id`, status — the two FK filters are dropdowns sourced the same way the Create form's pickers are, not a new pattern).

## 11. React Query Cache Strategy

Same as Sprint 15/16: list query keyed by `["subjects"/"grades"/"topics", "list", params]`, mutations invalidate the list key broadly. **New wrinkle**: Topics' cache should arguably also invalidate when its *dependency* data (Subjects/Grades lists) changes — but this is almost never actually necessary in practice (a Topic's stored `subject_id`/`grade_id` don't change just because the Subject was renamed elsewhere) and adding cross-module invalidation would be a real new pattern not requested — **not built** unless confirmed (see Outstanding Decisions).

## 12. RBAC / Permission Checks

**The one genuinely new pattern this sprint**: Topics' `canWrite` check must include `Teacher`, Subjects/Grades' must not (Finding #1). This can't be one shared boolean/hook reused blindly across all three pages — each page computes its own `canWrite` against its own module's real backend role list, same discipline as checking Sprint 15's Users/Sprint 16's Schools individually rather than assuming.

## 13. Form Validation Strategy

Client-side validation should mirror each backend validator's real constraint (min-length name checks, hex color format for Subjects' `color`, `order_number` being a real integer for Topics) — same "validate what the backend validates, not more, not less" discipline as every prior sprint's forms (`RegisterPage`, `SchoolFormPage`). No new validation *library* — plain HTML5 `required`/`minLength` plus the existing inline-error-on-submit pattern, matching Sprint 15/16's forms exactly.

## 14. Delete Confirmation Flow

`components/common/ConfirmDialog.tsx` reused directly, unchanged, exactly as it was built for in Sprint 16 — no new confirmation UI needed, the third consumer of this component.

## 15. Testing Strategy

Same style as Sprint 16: API wrapper tests (mocked `httpClient`), list page tests (rows, empty state, filters), **RBAC-gating tests for all three, but Topics' test must assert Teacher DOES see write controls while Subjects/Grades' tests assert Teacher does NOT** (the inverse of Sprint 16's Moderator test, and a genuinely new assertion direction, not a copy-paste of Sprint 16's test with the role name swapped) — this is the single most important test this sprint, given Finding #1 is the sprint's biggest risk of a silent bug.

---

## Risks

| Risk | Severity |
|---|---|
| **Topics' RBAC tier differs from Subjects/Grades** (Finding #1) — the single highest risk this sprint. If the same `canWrite` logic is copy-pasted across all three pages without adjustment, Teacher silently loses real, backend-granted write access on the Topics page. | High |
| **`StatusBadge`'s existing `STATUS_STYLES` map has no dedicated `archived` color** (only `active/inactive/banned/pending_verification` are styled) — verified directly. All three modules' `ALLOWED_STATUS_VALUES` are confirmed identical: `active, inactive, archived`. **Not a functional risk** — the component's existing fallback (`?? "bg-gray-100 text-gray-600"`) already renders `archived` correctly (same path Sprint 16's Schools/Learning Centers already exercised without issue), just without a visually-distinct color. A cosmetic-only note, resolved by inspection rather than assumption. | Low |
| **Topics' cross-module dropdown dependency** (Subjects, Grades lists) is architecturally new — if built carelessly, could turn into an accidental duplicate of `api/subjects.ts`/a new `api/grades.ts`'s own list logic instead of reusing it directly. | Low |
| **Grades' name-immutability** could be mis-implemented as "grayed out but present" (a disabled input) rather than the cleaner "not rendered as an editable field, shown as plain read-only text" — a UX nuance worth deciding explicitly rather than assumed. | Low |

---

## Outstanding Decisions — RESOLVED (approved)

1. **`api/grades.ts`/`api/topics.ts`**: confirmed neither existed, both built as new files matching `api/subjects.ts`'s style exactly.
2. **Subjects' `color`**: HTML5 `<input type="color">` — approved, no new UI library.
3. **"N ta mavzu" indicator**: not built — approved, no new aggregation, no frontend-computed count.
4. **Grades' `name`**: plain read-only text, never a disabled input — approved, tested explicitly.
5. **Topics cache**: fully isolated from Subjects/Grades mutations — approved, verified directly (no cross-references between the three hook files' query keys).

**Confirmed RBAC (verified against real backend `require_roles(...)` before writing any code)**:
- Subjects: Create/Edit/Delete = Super Admin, Admin. Teacher = read-only.
- Grades: Create/Edit/Delete = Super Admin, Admin. Teacher = read-only.
- Topics: Create/Edit/Delete = Super Admin, Admin, **Teacher**.

Implementation proceeds on this basis.

