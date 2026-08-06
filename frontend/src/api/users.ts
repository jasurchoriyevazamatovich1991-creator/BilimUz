/**
 * Users API wrapper. `count()` (Sprint 14) is unchanged below — this
 * file is EXTENDED for Sprint 15 (list/get/update/changeRole), not
 * replaced. Every shape verified against real backend
 * app/modules/users/{schemas,router}.py before writing.
 *
 * NOTE: no `create`/`delete` methods exist here — the backend has no
 * POST /users or DELETE /users/{id} endpoint (verified exhaustively,
 * see docs/Sprint15_Users_Management_UI_Architecture.md's Critical
 * Finding). Approved decision: List/View/Edit only this sprint.
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface UserOut {
  id: string;
  role_id: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  email: string | null;
  gender: string | null;
  birth_date: string | null;
  image: string | null;
  status: string;
  last_login: string | null;
  created_at: string;
}

export interface UserListParams {
  page: number;
  per_page: number;
  search?: string;
  role_id?: string;
  status?: string;
  sort?: string;
}

export interface UserAdminUpdateRequest {
  first_name?: string;
  last_name?: string;
  /** Only "active" | "inactive" are backend-settable (verified —
   * ADMIN_SETTABLE_STATUSES in users/constants.py). "banned" and any
   * other value are display-only elsewhere in the app, never sent here. */
  status?: "active" | "inactive";
}

export const usersApi = {
  count: async (): Promise<number> => {
    const result = await unwrap<PaginatedResponse<UserOut>>(httpClient.get("/users", { params: { per_page: 1 } }));
    return result.meta.total;
  },

  list: (params: UserListParams) => unwrap<PaginatedResponse<UserOut>>(httpClient.get("/users", { params })),

  get: (userId: string) => unwrap<UserOut>(httpClient.get(`/users/${userId}`)),

  update: (userId: string, data: UserAdminUpdateRequest) => unwrap<UserOut>(httpClient.patch(`/users/${userId}`, data)),

  /** Super-Admin-only on the backend (require_roles("Super Admin")) —
   * the UI must also gate this (see UserDetailPage.tsx), not rely on
   * the backend's 403 alone, matching the backend's own "never bundle
   * privilege escalation with an ordinary edit" design intent. */
  changeRole: (userId: string, roleId: string) => unwrap<UserOut>(httpClient.patch(`/users/${userId}/role`, { role_id: roleId })),
};
