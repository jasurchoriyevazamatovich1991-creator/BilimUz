# Sprint 15 — Users Management UI: Architecture Impact Analysis

**Status: DESIGN ONLY — no code written, no repository files modified, no ZIP.**

## Critical finding, established before any design choice below

**The backend Users module has no Create and no Delete endpoint — "CRUD" is not literally possible without a backend change.** Verified exhaustively (`app/modules/users/router.py` grepped for every `@router.` decorator — 6 total, listed below). Requested Sprint 15 scope (point 4: "CRUD architecture", point 9: "Delete confirmation flow") assumed a shape the backend doesn't have.

| Method | Path | Purpose | Auth |
|---|---|---|---|
| GET | `/users/me` | Own profile | Authenticated |
| PATCH | `/users/me` | Update own profile | Authenticated |
| GET | `/users` | List/search/filter | Admin, Super Admin |
| GET | `/users/{id}` | Get one | Admin, Super Admin |
| PATCH | `/users/{id}` | Admin-edit (name, status — active/inactive only) | Admin, Super Admin |
| PATCH | `/users/{id}/role` | Reassign role | **Super Admin only** |

**No `POST /users`** — a new user can only come into existence via `POST /auth/register` (self-registration + phone verification), never an Admin-initiated creation flow. **No `DELETE /users/{id}`** — no endpoint removes or deactivates-in-the-deletion-sense a user at all; the closest available action is `PATCH /users/{id}` with `status: "inactive"`.

**A second, smaller finding**: `users/constants.py` has a comment referencing a "dedicated `ban_user` endpoint" for the `banned` status — this endpoint **does not exist anywhere in the codebase** (verified — `BANNED` is a valid enum value on the `User` model, but nothing sets it). A vestigial/aspirational comment, not a real capability. `ADMIN_SETTABLE_STATUSES = ("active", "inactive")` confirms only these two are actually reachable via the API.

**This reframes Sprint 15 honestly as**: a **List + Search/Filter + View + Edit** UI (what the backend genuinely supports), not Create/Delete. Options for handling the gap are laid out in Outstanding Decisions, not assumed.

---

## 1. Existing Backend Users Module (full shape, confirmed above)

`UserOut`: `id, role_id, first_name, last_name, phone, email, gender, birth_date, image, status, last_login, created_at`. `UserListParams`: `page, per_page, search, role_id, status, sort` (sort field allowlist: `first_name, last_name, created_at, last_login`, verified in `constants.py`). `UserAdminUpdateRequest`: `first_name, last_name, status` only — **no `role_id`** (role changes are deliberately a separate, Super-Admin-only endpoint, "so privilege escalation is never bundled with an ordinary profile edit" per the backend's own docstring — a real, documented security design decision the frontend must respect, not route around).

## 2. Existing Frontend Foundation (Sprint 13) — reuse inventory

Already usable as-is, zero rebuild: `api/client.ts` (envelope unwrapping, token refresh), `store/authStore.ts`, `routes/ProtectedRoute.tsx`, `layouts/AdminLayout.tsx`, `components/ui/{button,input,card}.tsx` (shadcn primitives — **currently unused by any page**, this would be their first real consumer), `types/pagination.ts` (`PaginatedResponse<T>`, already matches `UserListParams`'s response shape exactly).

**`/admin/users` already exists as a route** — currently rendering the generic `<PlaceholderPage/>` via `AppRoutes.tsx`'s `placeholderRoutesFor(ADMIN_ITEMS, "/admin")` (unchanged mechanism). Sprint 15 replaces that one specific route's element with a real page — no new route-wiring code needed, same pattern already used for the Dashboard.

## 3. Existing Dashboard Architecture (Sprint 14) — reuse inventory

`DashboardCard`, `ErrorState`, `UnavailableState` (all three directly reusable — a users table page has the exact same loading/error/unavailable-data shape as a dashboard widget, just rendering a table instead of a number). `hooks/useDashboardStats.ts`'s pattern (TanStack Query + `useToastOnQueryError` via `useEffect`, not render-body) is the template to follow, not reuse directly (different data shape: paginated list vs. a count).

**`api/users.ts` already exists** but only has `count()` — Sprint 15 extends it (adds `list`, `get`, `update`), does not replace it or create a second file.

## 4. CRUD Architecture — revised to match reality

**List** (`GET /users`) + **Get** (`GET /users/{id}`) + **Update** (`PATCH /users/{id}`, name/status only) + **Role change** (`PATCH /users/{id}/role`, separate Super-Admin-gated action, not part of the edit form). **No Create form, no Delete flow** — see Outstanding Decisions #1 for how to handle this honestly in the UI (an "Add User" button with nothing behind it would be worse than not having one).

## 5. Users Table Architecture

A table (not cards — tabular data, many rows, matches the existing `panel_modules.md`-driven sidebar's own implicit assumption that admin screens are data-dense). Columns: Name (first+last), Phone/Email, Role (resolved from `role_id` via `GET /roles`, cached — same 8-role set already known from `utils/roleConfig.ts`, though that file maps role→panel, not role_id→name, so a **new**, small lookup is needed, not a duplicate of `roleConfig.ts`), Status (badge, colored per value), Last Login, row-click → detail/edit.

## 6. Search & Filtering

Maps directly to `UserListParams`: a search input (debounced — no existing debounce utility in the codebase, a small new one needed, see Outstanding Decisions #3), a role filter (dropdown, sourced from `GET /roles`), a status filter (`active`/`inactive` — matching `ADMIN_SETTABLE_STATUSES` exactly, not inventing a third option the backend can't filter on either, since `UserListParams.status` presumably accepts any string but only `active`/`inactive` are meaningful admin-settable values — `banned`/`pending_verification` etc. may exist as data but aren't admin-actionable).

## 7. Pagination

`PaginatedResponse<T>` (`types/pagination.ts`, already exists, already matches `{items, meta: {page, per_page, total, total_pages}}` exactly) — reused directly, no new pagination type.

## 8. Create/Edit Form Architecture

**Edit only** (per the finding above). Two genuinely separate concerns, matching the backend's own split: (a) a profile-edit form (`first_name`, `last_name`, `status` — maps to `UserAdminUpdateRequest`), (b) a role-change control, **Super-Admin-gated in the UI too**, not just relying on the backend to 403 an Admin who tries — matching the backend's own "never bundle privilege escalation with an ordinary edit" design intent at the UI layer as well.

## 9. Delete Confirmation Flow

**Does not apply — no delete capability exists.** See Outstanding Decisions #1.

## 10. React Query Cache Strategy

List query keyed by `["users", "list", params]` (params-inclusive key, standard TanStack pattern, already implicitly used by `useDashboardStats.ts`'s per-widget keys). On successful `PATCH`, invalidate `["users", "list"]` (all pages/filters) rather than manually patching cache — simpler, correct-by-construction, matches the project's existing "boring, correct" bias (e.g. Fernet over a custom cipher in the backend).

## 11. RBAC / Permission Checks

Route-level: `/admin/users` already sits inside `ProtectedRoute allowedPanel="admin"` (unchanged) — covers Admin, Super Admin, Moderator (per `roleConfig.ts`'s existing panel mapping). **Component-level, new**: the role-change control must check for `Super Admin` specifically (not just "is in the admin panel") — `Moderator` and plain `Admin` can view the table and edit name/status, but must not see/use the role-change control. This is UI convenience only, same explicit caveat as `ProtectedRoute` — the backend's `require_roles("Super Admin")` on `PATCH /users/{id}/role` remains the actual enforcement.

## 12. Testing Strategy

`api/users.ts` extensions: mocked-`httpClient` tests for `list`/`get`/`update`, same style as `client.test.ts`. Table component: renders rows from mock data, empty state, error state (reusing `ErrorState`). Search/filter: debounce timing (fake timers, same technique already used in `toastStore.test.ts`'s auto-dismiss test), filter params correctly passed to the query. Role-change gating: Super Admin sees the control, Admin/Moderator don't (same assertion style as `ProtectedRoute.test.tsx`'s role-based rendering checks).

---

## Risks

| Risk | Severity |
|---|---|
| **"CRUD" was requested but Create/Delete don't exist on the backend** — the single most consequential finding this sprint; must be resolved as a product decision, not silently worked around. | High |
| **No debounce utility exists anywhere in the codebase yet** — a small, genuinely new piece of infrastructure (not a duplicate of anything), low risk in isolation but worth naming since "reuse everything" was emphasized and this is the one clear exception. | Low |
| **Role-name resolution (`role_id` → display name) has no existing frontend home** — `roleConfig.ts` maps role *name* → panel, not id → name; a small new lookup (reading `GET /roles` once, cached) is needed, distinct from and not a duplicate of `roleConfig.ts`. | Low |
| **shadcn/ui primitives (`Button`, `Input`, `Card`) have zero real consumers today** — Sprint 15 would be their first actual use; if they have any latent issues (untested since creation), this is where they'd first surface. | Low |

---

## Outstanding Decisions — RESOLVED (approved)

1. **Create/Delete gap**: Option (A) — List/View/Edit only this sprint. No Create button, no Delete button, no disabled/hidden placeholders for either.
2. **Delete semantics — explicitly deferred, future consideration only** (not designed this sprint, not this sprint's decision): whenever a future sprint adds real delete/deactivate capability, it will need to choose between a hard `DELETE /users/{id}` (matching every other module's soft-delete convention, if applied consistently) versus repurposing `PATCH .../status=inactive` as the de facto "remove" action. Recorded here only so a future sprint doesn't have to rediscover the question — no design work toward either option happens now.
3. **Debounce utility**: approved — new, minimal `hooks/useDebouncedValue.ts`, no external library.
4. **Role-name lookup**: approved — new `hooks/useRoles.ts` + `api/roles.ts`, NOT an extension of `utils/roleConfig.ts`.
5. **`banned` status**: UI displays whatever value the backend returns, including `banned` — no ban/unban action built, status never hidden or reinterpreted.

Implementation proceeds on this basis.

