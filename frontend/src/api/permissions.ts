/**
 * New API wrapper — full Permission CRUD + Role<->Permission grant
 * management. Every path verified DIRECTLY against real backend
 * app/modules/permissions/router.py before writing this file.
 *
 * IMPORTANT MISMATCH FOUND AND CORRECTED: the implementation brief
 * assumed `/roles/{role_id}/permissions` — the REAL backend paths are
 * under the permissions router instead:
 *   GET    /permissions/roles/{role_id}
 *   POST   /permissions/roles/{role_id}/assign
 *   DELETE /permissions/roles/{role_id}/revoke/{permission_id}
 * (the DELETE also takes permission_id as a second path param, not
 * just role_id — the brief's assumed shape omitted it entirely). Used
 * as verified here, not as originally assumed.
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface PermissionOut {
  id: string;
  name: string;
  code: string;
  module: string;
  description: string | null;
  status: string;
  created_at: string;
}

export interface PermissionListParams {
  page: number;
  per_page: number;
  search?: string;
  module?: string;
  status?: string;
  sort?: string;
}

export interface PermissionCreateRequest {
  name: string;
  code: string;
  module: string;
  description?: string;
}

export interface PermissionUpdateRequest {
  /** `code` is intentionally absent — matches the real backend
   * PermissionUpdateRequest exactly (immutable, every
   * require_permission('CODE') call depends on it staying stable). */
  name?: string;
  description?: string;
  status?: string;
}

export interface RolePermissionOut {
  id: string;
  role_id: string;
  permission_id: string;
  /** Embedded by the backend — no separate lookup needed to show the
   * permission's name/code/module for an assigned grant. */
  permission: PermissionOut | null;
  created_at: string;
}

export const permissionsApi = {
  list: (params: PermissionListParams) => unwrap<PaginatedResponse<PermissionOut>>(httpClient.get("/permissions", { params })),

  get: (permissionId: string) => unwrap<PermissionOut>(httpClient.get(`/permissions/${permissionId}`)),

  create: (data: PermissionCreateRequest) => unwrap<PermissionOut>(httpClient.post("/permissions", data)),

  update: (permissionId: string, data: PermissionUpdateRequest) =>
    unwrap<PermissionOut>(httpClient.patch(`/permissions/${permissionId}`, data)),

  remove: (permissionId: string) => httpClient.delete(`/permissions/${permissionId}`),

  listForRole: (roleId: string) => unwrap<RolePermissionOut[]>(httpClient.get(`/permissions/roles/${roleId}`)),

  assignToRole: (roleId: string, permissionId: string) =>
    unwrap<RolePermissionOut>(httpClient.post(`/permissions/roles/${roleId}/assign`, { permission_id: permissionId })),

  revokeFromRole: (roleId: string, permissionId: string) =>
    httpClient.delete(`/permissions/roles/${roleId}/revoke/${permissionId}`),
};
