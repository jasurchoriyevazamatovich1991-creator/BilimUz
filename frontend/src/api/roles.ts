/**
 * New API wrapper — GET /roles, Admin/Super Admin only (verified
 * against backend/app/modules/roles/router.py before writing this
 * file). Only 8 roles exist total (seeded, see
 * database/schema/schema_v2.sql) — a single per_page=100 call covers
 * all of them, no pagination UI needed for this lookup use case.
 *
 * Sprint 22 extension: `list()` (Sprint 15) is UNCHANGED below —
 * hooks/useRoles.ts's existing useRoles()/useRoleNameLookup() depend on
 * its exact no-args, items-only shape (consumed by UsersListPage.tsx
 * and TopicsListPage.tsx). A separate `listPaginated()` is added for
 * the new RolesListPage.tsx instead of altering `list()`'s signature.
 *
 * NOTE: `name` is intentionally absent from RoleUpdateRequest below —
 * matches the real backend RoleUpdateRequest exactly (verified — no
 * `name` field exists; renaming is handled as create-new + migrate,
 * never an in-place edit, since every require_roles("Exact Name") call
 * across the codebase depends on the name staying stable).
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface RoleOut {
  id: string;
  name: string;
  description: string | null;
  status: string;
  created_at?: string;
}

export interface RoleListParams {
  page: number;
  per_page: number;
  search?: string;
  status?: string;
  sort?: string;
}

export interface RoleCreateRequest {
  name: string;
  description?: string;
}

export interface RoleUpdateRequest {
  description?: string;
  status?: string;
}

export const rolesApi = {
  list: async (): Promise<RoleOut[]> => {
    const result = await unwrap<PaginatedResponse<RoleOut>>(httpClient.get("/roles", { params: { per_page: 100 } }));
    return result.items;
  },

  listPaginated: (params: RoleListParams) => unwrap<PaginatedResponse<RoleOut>>(httpClient.get("/roles", { params })),

  get: (roleId: string) => unwrap<RoleOut>(httpClient.get(`/roles/${roleId}`)),

  create: (data: RoleCreateRequest) => unwrap<RoleOut>(httpClient.post("/roles", data)),

  update: (roleId: string, data: RoleUpdateRequest) => unwrap<RoleOut>(httpClient.patch(`/roles/${roleId}`, data)),

  remove: (roleId: string) => httpClient.delete(`/roles/${roleId}`),
};
