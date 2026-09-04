# Sprint 22 — Roles + Permissions UI

**Status: BUILD PASS, TESTS PASS, READY FOR REVIEW**

## 1. Sprint goal

Build a complete Super Admin UI for Roles management, Permissions management, and Role↔Permission assignment/revocation — against real, already-implemented backend endpoints, with system-role protection enforced in the UI to match the backend's own strict rules.

## 2. Scope

- Roles: list, view/edit, create, delete
- Permissions: list, view/edit, create, delete
- Role↔Permission: view assigned, assign, revoke

**Write access is Super Admin only** — a narrower tier than every prior CRUD sprint (Subjects/Grades/Schools allowed Admin+SuperAdmin; Topics/Lessons/Tests allowed Teacher too). Verified fresh against this module's own backend, not assumed from those precedents.

## 3. Backend endpoints — one real mismatch found and corrected

Every path verified directly against `app/modules/{roles,permissions}/router.py` before writing any code.

| Endpoint | Verified path |
|---|---|
| List/get/create/update/delete roles | `GET/GET/POST/PATCH/DELETE /roles`, `/roles/{id}` |
| List/get/create/update/delete permissions | `GET/GET/POST/PATCH/DELETE /permissions`, `/permissions/{id}` |
| List a role's permissions | `GET /permissions/roles/{role_id}` |
| Assign a permission to a role | `POST /permissions/roles/{role_id}/assign` |
| Revoke a permission from a role | `DELETE /permissions/roles/{role_id}/revoke/{permission_id}` |

**Mismatch found**: the implementation brief assumed `/roles/{role_id}/permissions`-style paths. The real backend nests all three role↔permission endpoints under the **permissions** router instead (`/permissions/roles/{role_id}`), and the revoke endpoint takes **both** `role_id` and `permission_id` as path parameters, not just `role_id`. The real, verified paths were used throughout — not the assumed ones.

## 4. Roles UI

`RolesListPage.tsx`: search, status filter, pagination — all match real `RoleListParams` exactly (no invented filters). Each row shows a "Tizim roli" / "Maxsus" indicator. `RoleFormPage.tsx` handles Create and Edit in one page (matching the Sprint 15–19 convention): `name` is **plain read-only text in edit mode for every role, system or custom** — the real backend `RoleUpdateRequest` has no `name` field at all, for any role.

## 5. Permissions UI

`PermissionsListPage.tsx`: search, module filter (built from loaded data via the existing `deriveDistinctValues`, Sprint 16), status filter, pagination. `PermissionFormPage.tsx`: `code` is plain read-only text in edit mode — the real backend `PermissionUpdateRequest` has neither `code` nor `module`, both verified immutable (same reasoning as Roles' `name`).

## 6. Role-permission management

Embedded directly in `RoleFormPage.tsx`'s edit mode (matching `QuestionFormPage.tsx`'s Sprint 19 precedent of hosting sub-resource management on the parent's own edit page) — not a separate page. Each assign/revoke is its **own immediate API call** (no batching, unlike Sprint 19's Options editor) — there is no bulk endpoint, and unlike a multi-field form being composed, each grant/revoke here is already a single, complete, independent action with its own toast feedback. The "available to assign" dropdown is pre-filtered to exclude already-assigned permissions client-side, which naturally prevents most duplicate-assign attempts; a genuine race (409 `RolePermissionAlreadyExistsException`) is still handled gracefully via the normal toast path, tested explicitly.

## 7. RBAC

`canWrite = currentUser?.role === "Super Admin"` — computed independently in every page (matching the established "each module checks its own real backend role list" discipline), never copy-pasted from a wider tier. Read access (list/get) follows the backend's own `Admin, Super Admin` tier — a plain Admin can view roles/permissions/grants but sees no write controls anywhere (buttons hidden entirely, never shown disabled).

## 8. System role protection — verified precisely, not guessed

`utils/systemRoles.ts` mirrors `backend/app/modules/roles/constants.py::SYSTEM_ROLE_NAMES` **exactly** (verified directly against the source): `Super Admin, Admin, Moderator, Teacher, Applicant, Student, Parent, Guest`. This is reliable because role names are proven immutable (no `name` field on `RoleUpdateRequest` at all) — the same reasoning already used for `utils/roleConfig.ts`'s role→panel map.

**A stricter-than-expected backend rule was found while reading `roles/service.py`**: system roles can't just not-be-deleted — `update_role()` also rejects any `status` change away from `"active"` for a system role (not only deletion). Only `description` is genuinely editable for one. The UI reflects this precisely: for a system role, `status` renders as plain read-only text (not a disabled select), and no Delete button is rendered at all.

## 9. API / hooks

**Extended, existing behavior unchanged**: `api/roles.ts` — Sprint 15's `list()` (no-args, items-only) is byte-for-byte untouched (still depended on by `UsersListPage.tsx`/`TopicsListPage.tsx`); a separate `listPaginated()` was added instead of altering its signature. `hooks/useRoles.ts` — Sprint 15's `useRoles()`/`useRoleNameLookup()` unchanged; new CRUD hooks added below them.

**New**: `api/permissions.ts`, `hooks/usePermissions.ts` (full CRUD + `useRolePermissions`/`useAssignPermission`/`useRevokePermission`).

Query keys follow the established convention (`["roles", "list-paginated", params]`, `["permissions", "for-role", roleId]`, etc.); mutations invalidate the relevant keys on create/update/delete/assign/revoke. Same single app-wide `QueryClient` used throughout — no second client created.

## 10. Routes

```
/admin/roles, /admin/roles/new, /admin/roles/:roleId
/admin/permissions, /admin/permissions/new, /admin/permissions/:permissionId
```

Wired via the existing `placeholderRoutesFor()`/`excludePaths` mechanism (Sprint 15–19 precedent) — no new routing infrastructure. All sit inside the existing `ProtectedRoute allowedPanel="admin"`.

## 11. Sidebar

**No changes needed** — "Rollar" (`/admin/roles`) and "Ruxsatlar" (`/admin/permissions`) already existed in `ADMIN_ITEMS` from Sprint 13's original scaffold, previously pointing at `PlaceholderPage`. Only `AppRoutes.tsx`'s `excludePaths` list was extended to swap them for the real pages.

## 12. UI / design

No new colors, no dark mode, no theme work — existing `Button`, `Card`, `Input`, `StatusBadge`, `ConfirmDialog`, and Tailwind tokens reused throughout, matching every prior CRUD sprint's visual shape exactly.

## 13. Security

- Ownership/RBAC enforced server-side throughout — the frontend's `canWrite` gating is UX convenience only, never the actual security boundary (same explicit discipline as every prior sprint).
- System-role protection is a real backend rule (`SystemRoleProtectedException`, 403) — the frontend UI matches it but the backend remains authoritative regardless of what the UI shows.
- `ConfirmDialog` used for every destructive action (role delete, permission delete, permission revoke) — never a raw `window.confirm()`.
- No sensitive data exposed — `RoleOut`/`PermissionOut` carry no PII.

## 14. Tests

37 new tests across 6 files; all 23 requested scenarios covered (existing Sprint 13–21 tests untouched).

**Roles** (`RolesListPage.test.tsx`, `RoleFormPage.test.tsx`): list success/empty/error, create, edit custom role, system role name read-only, system role has no delete action, delete-custom-role via `ConfirmDialog`, non-Super-Admin sees no write controls.

**Permissions** (`PermissionsListPage.test.tsx`, `PermissionFormPage.test.tsx`): list success/empty/error, create, edit, delete via `ConfirmDialog`.

**Role↔Permissions** (in `RoleFormPage.test.tsx`): loads assigned grants, assigns with the real request body, revokes via `ConfirmDialog`, a 409 duplicate-assignment is surfaced via the normal toast without crashing.

**Routing/RBAC**: Super Admin sees write controls, plain Admin does not (list and detail both), plain Admin is redirected away from the Create route.

**Regression**: full suite re-run.

```
Test Files: 34 passed (34)
Tests:      170 passed (170)
```

## 15. Build

```
TypeScript: PASS
Build:      PASS (dist/ produced, 249 modules — up from 242 in Sprint 21)
```

## 16. Known limitations

- No bulk permission assignment (matches the real backend — no such endpoint exists).
- No pagination UI for the "available to assign" permissions dropdown inside `RoleFormPage.tsx` (fetched with `per_page: 100`, matching the established reference-data convention from Sprint 19's Subject/Grade/Topic pickers) — would need real pagination if the permission catalog ever grows past 100.
- `RoleOut`/`PermissionOut` have no explicit `is_system`/`is_immutable` flag from the backend — the frontend's system-role detection relies on matching the known, verified `SYSTEM_ROLE_NAMES` list rather than a dedicated backend field.

## 17. Future improvements

- A dedicated backend `is_system: bool` field on `RoleOut` would remove the frontend's reliance on mirroring a name list (a real, if minor, backend enhancement candidate for a future sprint — not built here, per "do not modify backend").
- Bulk-assign UI, if the backend ever adds a bulk endpoint.
- Permission catalog pagination in the Role edit page's picker, if the catalog grows.
