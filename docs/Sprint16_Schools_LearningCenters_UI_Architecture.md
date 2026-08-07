# Sprint 16 — Schools & Learning Centers UI: Architecture Impact Analysis

**Status: DESIGN ONLY — no code written, no repository files modified, no ZIP.**

## Key finding, established before any design choice below

**Unlike Sprint 15's Users module, Schools and Learning Centers have FULL CRUD on the backend** — `GET` (list, public), `GET` (one, public), `POST` (create, Admin/Super Admin), `PATCH` (update, Admin/Super Admin), `DELETE` (soft delete, Admin/Super Admin). Verified exhaustively against both routers. This means Sprint 16 can legitimately build Create, Edit, **and** Delete UI — the Sprint 15 constraint does not carry over, and assuming it would under-deliver against what the backend actually supports.

**A second finding**: neither module has a sidebar entry today. `utils/sidebarConfig.ts`'s `ADMIN_ITEMS` has no "Maktablar" or "O'quv markazlari" row — unlike Users (which already had one from Sprint 13's original scaffold, later upgraded from placeholder to real page in Sprint 15). Sprint 16 needs to *add* two new sidebar entries (small, justified extension, same precedent as Sprint 14's `Profil`/`Sozlamalar` additions), not just swap an existing placeholder for a real page.

---

## 1–2. Existing Backend Modules (confirmed identical CRUD shape, structurally near-twins)

| | Schools | Learning Centers |
|---|---|---|
| Fields (beyond id/status/timestamps) | `name, region, district, address, phone` | `name, owner_name, phone, region` |
| List params | `page, per_page, search, region, district, status, sort` | `page, per_page, search, region, status, sort` |
| Create/Update auth | Admin, Super Admin | Admin, Super Admin |
| List/Get auth | Public | Public |
| Delete | Soft delete (`DELETE`, Admin/Super Admin) | Soft delete (`DELETE`, Admin/Super Admin) |
| `ALLOWED_STATUS_VALUES` | `active, inactive, archived` | `active, inactive, archived` |

Both were built in Sprint 10 as deliberately-parallel-but-separate modules (schema's own module boundary, same reasoning as not merging `grades`/`topics`/`lessons`). The frontend should mirror that: two pages, not one generic "institution" abstraction — premature abstraction over two modules that happen to look similar today risks the same trap the backend explicitly avoided.

## 3. Existing Frontend Architecture (Sprints 13–15) — what Sprint 16 builds on

Every piece of infrastructure needed already exists and requires no new invention: `api/client.ts` (unwrap, token refresh), `routes/ProtectedRoute.tsx`, `AdminLayout`, `types/pagination.ts`. **`api/schools.ts` and `api/learningCenters.ts` already exist** (built in Sprint 14 for the Admin dashboard widgets) but only have a `count()` method — Sprint 16 *extends* them (adds `list/get/create/update/remove`), exactly the same pattern Sprint 15 used to extend `api/users.ts` without touching its existing `count()`.

## 4. Existing Reusable Components — full inventory, all directly applicable

`components/ui/{button,input,card}.tsx` (shadcn primitives, real consumers since Sprint 15), `components/layout/{ErrorState,UnavailableState,PlaceholderPage}.tsx`, `components/users/StatusBadge.tsx` (built for Users' 4-value status enum — **directly reusable as-is** for Schools/Learning Centers' 3-value enum `active/inactive/archived`, since the component already renders any string it's given, no Users-specific logic inside it), `hooks/useDebouncedValue.ts`, `hooks/useRoles.ts` (NOT applicable here — schools/centers have no role concept, not reused, correctly excluded rather than force-fit).

**The Users list table itself (`UsersListPage.tsx`) is the structural template**, not a component to import — its table/search/filter/pagination shape is copied conceptually (same as `grades`/`topics`/`lessons` sharing a CRUD *shape* on the backend without sharing code), not abstracted into a shared "generic admin table" component this sprint (see Outstanding Decisions #1 — a real design choice, not assumed).

## 5–6. Schools List / Learning Centers List Architecture

Same shape as `UsersListPage`, two separate page components (`SchoolsListPage.tsx`, `LearningCentersListPage.tsx`) — table with Name, Region (+ District for Schools / + Owner for Centers), Phone, Status (`StatusBadge`, reused directly), row-click → detail. **Unlike Users, these tables also need an "Add" button and each row a delete affordance** — genuinely new UI this sprint, since Users never had one (no backend support there) but these two modules do.

## 7. Search & Filtering

Maps directly to each module's real `ListParams`: search input (debounced via `useDebouncedValue`, reused directly), region filter (free-text `select`, no controlled vocabulary exists in the schema — same "flat, not hierarchical" limitation already documented in Sprint 10's README), status filter (`active/inactive/archived` — all three, unlike Users where only `active/inactive` were admin-settable; here all three genuinely are, since `SchoolUpdateRequest.status` accepts any of `ALLOWED_STATUS_VALUES`). Schools additionally gets a District filter.

## 8. Pagination

`types/pagination.ts`'s `PaginatedResponse<T>` reused directly — no new pagination type, matches both modules' response shape exactly (verified).

## 9. View/Edit/Create/Delete Architecture

**Create**: a form (name + module-specific fields + optional phone/region) — genuinely new, since Sprint 15 had no Create form to pattern-match against structurally (though the *field-level* patterns — labeled `Input`, validation messaging — carry over from `RegisterPage.tsx`/`UserDetailPage.tsx`'s edit form). **Edit**: same form, pre-filled, `PATCH`. **Delete**: a confirmation step before calling `DELETE` — the first delete-confirmation UI anywhere in the frontend (Sprint 15 explicitly had none) — needs a real confirm dialog, not a bare `window.confirm()` (inconsistent with the shadcn/ui-styled rest of the app), so a small new `ConfirmDialog` component is needed (see Outstanding Decisions #2).

## 10. React Query Cache Strategy

Same as Sprint 15's `useUsers.ts`: list query keyed by `["schools", "list", params]` / `["learningCenters", "list", params]`, mutations (create/update/delete) invalidate the list key broadly rather than manually patching cache entries — same "boring, correct" bias already established.

## 11. RBAC / Permission Checks

Route-level: `/admin/schools` and `/admin/learning-centers` sit inside the existing `ProtectedRoute allowedPanel="admin"` (unchanged) — reachable by Super Admin, Admin, **and Moderator** (per `roleConfig.ts`'s existing panel mapping). **Component-level, new**: Create/Edit/Delete controls must be hidden for `Moderator`, since the backend's `require_roles("Admin", "Super Admin")` on write endpoints excludes Moderator — unlike Sprint 15's role-change (which was Super-Admin-only, a narrower cut), this is a two-tier gate (Admin+SuperAdmin can write, Moderator+everyone-in-the-panel can only read) that doesn't exactly match any existing frontend gating pattern yet (`ProtectedRoute` gates by *panel*, not by *role-within-panel* for write actions) — a small, genuinely new check, not a duplicate of anything.

## 12. Testing Strategy

Same style as Sprint 15: `api/schools.ts`/`api/learningCenters.ts` extension tests (mocked `httpClient`), list page tests (renders rows, empty state, search/filter params passed correctly — reusing the exact test patterns from `UsersListPage.test.tsx`), **new**: Create/Edit form validation tests, Delete confirmation flow tests (dialog opens, cancel doesn't delete, confirm calls the mutation), Moderator-cannot-see-write-controls test (parallel to Sprint 15's Super-Admin-gating test for role-change).

---

## Risks

| Risk | Severity |
|---|---|
| **Two near-identical modules risk copy-paste drift** if built as fully separate, unabstracted code (same risk the backend accepted in Sprint 10 for the same reason) — worth naming even though the recommended approach (Outstanding Decision #1) accepts this trade-off deliberately. | Low |
| **First delete-confirmation UI in the frontend** — no existing `ConfirmDialog` pattern to reuse, a genuinely new small component; if built loosely, could be copy-pasted three more times in a future sprint instead of being properly reusable now. | Medium |
| **No sidebar entries exist yet for either module** — two new `ADMIN_ITEMS` rows needed, same category of change as Sprint 14/15's small sidebar extensions, low risk in isolation but worth tracking since "don't touch Sprint 13 files" keeps needing small, repeated exceptions. | Low |
| **Region/District are free-text, no controlled vocabulary** (documented limitation since Sprint 10) — a filter dropdown built from *distinct values already in the data* (not a fixed list) could be inconsistent/inaccurate ("Toshkent" vs "toshkent" both existing) — the filter would work but wouldn't be as clean as a real controlled list. | Low |

---

## Outstanding Decisions — RESOLVED (approved)

1. **Two separate pages**, not one generic component — approved.
2. **`ConfirmDialog`** — approved, built as `components/common/ConfirmDialog.tsx`, reusable for future Delete flows.
3. **Region filter**: dropdown built from distinct values in the currently-loaded page (no new backend endpoint) — approved.
4. **Moderator write-gating**: Create/Edit/Delete controls hidden entirely, never shown disabled — approved. Implementation note: this was refined during coding — Moderator can still *view* an existing school/center (backend's GET is public), only the write controls (Save/Delete buttons, all form fields) are hidden/disabled; only the Create route is fully off-limits.
5. **Sidebar order**: `Dashboard, Users, Schools, Learning Centers, Rollar, Ruxsatlar, Subjects, ...` — approved insertion point (right after Users), existing entries (Rollar, Ruxsatlar, etc.) retained in their original relative order since the approved list was illustrative of placement, not an exhaustive replacement.

Implementation proceeds on this basis.

