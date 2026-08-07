# Sprint 18 — Lessons UI: Architecture Impact Analysis

**Status: DESIGN ONLY — no code written, no repository files modified, no ZIP.**

## Key findings, established before any design choice below

**1. `api/lessons.ts` already exists** — unlike Sprint 17's Grades/Topics (new files) but matching Subjects' pattern, Sprint 14 built a `count()`-only starter file for the Teacher dashboard widget. Sprint 18 **extends** it, does not create it fresh.

**2. A genuinely new cross-field validation rule** — `LessonCreateRequest` has a `model_validator` requiring **at least one of `video`, `pdf`, `content`** to be non-empty (verified against the real backend schema). No prior CRUD sprint's Create form had a "pick at least one of several optional fields" constraint — Schools/Subjects/Grades/Topics all just needed one required name/title field. This must be mirrored client-side (disable submit or show a clear inline message when all three are empty), not just left to the backend's 422 to surface awkwardly.

**3. RBAC matches Topics exactly, not Subjects/Grades** — `require_roles("Admin", "Super Admin", "Teacher")` on all three write endpoints, verified directly. Sprint 17's `TopicsListPage.tsx`/`TopicFormPage.tsx` `canWrite` logic (`role === "Admin" || "Super Admin" || "Teacher"`) is the correct pattern to repeat here — not Sprint 16/17's narrower Subjects/Grades/Schools tier.

**4. `topic_id` is required on create, absent from `LessonUpdateRequest` entirely** — same immutable-parent shape as Topics' own `subject_id`, one level deeper (Lesson → Topic → Subject/Grade). The Lessons form needs a Topic picker (read-only lookup into `api/topics.ts`, built in Sprint 17), the second cross-module dropdink dependency after Topics' own Subject/Grade pickers.

**5. Sidebar entry already exists** (`Darslar → /admin/lessons`, `/student/lessons`) — no new `ADMIN_ITEMS` row needed, same situation as Sprint 17's Subjects/Grades/Topics, not Sprint 16's Schools/Learning Centers.

---

## 1. Existing Backend Lessons Module

Full CRUD (`GET/GET/POST/PATCH/DELETE`). `LessonOut`: `id, topic_id, title, video, pdf, content, status, created_at, updated_at`. `LessonListParams`: `page, per_page, search, topic_id, status, sort` — a `topic_id` filter exists, same shape as Topics' own `subject_id`/`grade_id` filters. `video`/`pdf` are validated as URLs (`validate_media_url`) when present — a third, new-to-this-sprint field-level validation type (beyond plain length checks and Subjects' hex-color check).

## 2. Existing Frontend Architecture (Sprints 13–17) — what Sprint 18 builds on

Everything needed exists: `api/client.ts`, `ProtectedRoute`, `AdminLayout`, `types/pagination.ts`, `components/common/ConfirmDialog.tsx`, `components/users/StatusBadge.tsx` (Lessons' `ALLOWED_STATUS_VALUES` needs a direct check — see Outstanding Decisions, not assumed identical to the `active/inactive/archived` set every prior module happened to share), `hooks/useDebouncedValue.ts`, and critically `hooks/useTopics.ts`/`api/topics.ts` (Sprint 17) for the Topic picker — read-only, same one-directional dependency shape Topics itself used for Subjects/Grades.

## 3. Existing Reusable CRUD Patterns (fourth application of the same shape)

`api/lessons.ts` (extend, don't replace `count()`) → `hooks/useLessons.ts` (list/get/create/update/delete, toast-via-`useEffect`, list-key invalidation — copy the exact shape of `hooks/useTopics.ts`) → `pages/admin/LessonsListPage.tsx` + `pages/admin/LessonFormPage.tsx` (shared Create/Edit, read-only rendering for non-writers, Topic picker instead of a Subject/Grade pair). No new pattern invented — the fourth consecutive sprint following the identical Sprint 15→16→17 shape.

## 4. Lessons UI Architecture

List: Title, Topic (resolved via read-only Topics lookup, same technique Topics used for Subject/Grade names), Content indicators (small icons/badges for "has video" / "has PDF" / "has text" — a natural, low-cost way to show the at-least-one-of-three content state at a glance, not required by the backend but a reasonable UX addition — see Outstanding Decisions), Status, row-click → detail.

## 5. Lesson ↔ Topic Relationship

Same shape as Topics ↔ Subjects/Grades (Finding #4): a required, set-once `topic_id` on create, a dropdown sourced from `hooks/useTopics.ts`'s list (read-only), no write access to Topics from this page. One layer deeper in the hierarchy (Subject → Topic → Lesson) than anything built so far, but the *pattern* is identical, not a new one.

## 6. Search, Filtering, Pagination

`PaginatedResponse<T>` reused directly (verified — `LessonListParams`'s response shape matches exactly, same as every prior module). Filters: search, Topic (dropdown, same source as the form's picker), status.

## 7. Create/Edit/Delete Flow

Create: Topic picker (required) + title + video/pdf/content (client-side "at least one" check, Finding #2) . Edit: same fields minus Topic (immutable) plus status — note this is **structurally different from Grades'** "only status is editable" (Lessons' title/video/pdf/content ARE all editable post-creation, only the Topic relationship is fixed) — closer to Subjects' shape (most fields editable, one relationship/identity field locked) than Grades' shape (almost everything locked). Delete: `ConfirmDialog`, unchanged, fourth consumer.

## 8. React Query Cache Strategy

Same as Sprint 17: `["lessons", "list", params]` / `["lessons", "detail", id]`, mutations invalidate the list key broadly. **Same isolation discipline as Topics' cache (Sprint 17, approved decision 5)**: Lessons' own CRUD invalidates only `["lessons", ...]`; reading Topics for the picker never triggers or depends on Topics' cache being invalidated by Lessons' mutations, and vice versa.

## 9. RBAC / Permission Checks

`canWrite = role === "Admin" || role === "Super Admin" || role === "Teacher"` — copy Topics' exact tier (Finding #3), computed independently for this module (not imported/shared from Topics' page, matching the established "each page checks its own module's real backend role list" discipline from Sprint 17).

## 10. Form Validation Strategy

Mirrors each backend validator: title length, URL-format checks for `video`/`pdf` (new field type this sprint — a plain `type="url"` HTML5 input is the natural, no-new-library match), and the cross-field "at least one of video/pdf/content" rule (Finding #2) shown as a single inline message near the three fields, checked on submit (same "validate what the backend validates, not more" discipline as every prior sprint).

## 11. Delete Confirmation Flow

`ConfirmDialog`, unchanged, reused directly — no new confirmation UI.

## 12. Sidebar Integration

**None needed** — `Darslar` already exists in both `ADMIN_ITEMS` and the Teacher/Student sidebars (Finding #5). `routes/AppRoutes.tsx` gets `/admin/lessons` swapped from `PlaceholderPage` to the real page via the existing `excludePaths` mechanism (Sprint 15/16/17 precedent) — no new routing infrastructure.

## 13. Error Handling

Same as every prior sprint: `ErrorState` for failed list/detail fetches, toast (existing `store/toastStore.ts`) for mutation failures — no new error-handling pattern.

## 14. Testing Strategy

Same shape as Sprint 17: API wrapper tests, list page tests (rows, empty state, filters), RBAC test (Teacher DOES see write controls, matching Topics' precedent — **not** Subjects/Grades' opposite result, so this must be asserted explicitly, not assumed from "it's a content module so it's probably like Subjects"), and a **new** test category: the "at least one of video/pdf/content" client-side validation (submit blocked/flagged when all three are empty, allowed when any one is filled).

## 15. Reusable Components — confirmed inventory

`ConfirmDialog`, `StatusBadge`, `useDebouncedValue`, the `ListPage`/`FormPage` structural pattern, `hooks/useTopics.ts` (read-only, for the picker) — all reused. **No new shared component is anticipated this sprint** (unlike Sprint 16's `ConfirmDialog` or Sprint 17's `deriveDistinctValues`) — Lessons is the first sprint in this series that appears to need zero new reusable infrastructure, only new module-specific files following the established shape.

---

## Risks

| Risk | Severity |
|---|---|
| **The "at least one of video/pdf/content" rule is easy to miss** if the Create form is built by pattern-matching Topics'/Subjects' single-required-field shape without reading `LessonCreateRequest`'s `model_validator` — the single highest risk this sprint, parallel to Sprint 17's Topics-RBAC risk. | High |
| **RBAC tier mis-copied from Subjects/Grades instead of Topics** — same class of risk as Sprint 17, now with two prior "narrow" examples (Subjects, Grades) and one "wide" example (Topics) to potentially confuse. | Medium |
| **`StatusBadge` coverage unverified for Lessons' actual `ALLOWED_STATUS_VALUES`** — likely identical `active/inactive/archived` given every module so far has matched, but not yet directly confirmed for Lessons specifically. | Low |
| **Content-type indicator icons (video/pdf/content presence)** are a UX nicety not strictly requested — if built, adds minor scope; if skipped, no functional loss. | Low |

---

## Outstanding Decisions — RESOLVED (approved)

1. **Confirmed directly**: Lessons' `ALLOWED_STATUS_VALUES` identical to every prior module — `StatusBadge` unchanged.
2. **Content-type indicators**: built — `components/lessons/ContentBadges.tsx`, only rendered for present fields, matching `StatusBadge`'s pill style.
3. **`video`/`pdf` input type**: native `<input type="url">` — approved.
4. **"At least one of video/pdf/content" UX**: submit-time check, never a disabled button — approved, matches the existing project convention.

**Confirmed RBAC (verified against real backend `require_roles(...)` before writing any code)**: Lessons Create/Edit/Delete = Super Admin, Admin, Teacher. Student = read-only.

Implementation proceeds on this basis.

