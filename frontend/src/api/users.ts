/**
 * Minimal wrapper for this sprint's need: the users COUNT for the Admin
 * dashboard widget (GET /users, Admin/Super Admin only, verified
 * against the real backend/app/modules/users/router.py before writing
 * this file — not assumed).
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
  status: string;
}

export const usersApi = {
  count: async (): Promise<number> => {
    const result = await unwrap<PaginatedResponse<UserOut>>(httpClient.get("/users", { params: { per_page: 1 } }));
    return result.meta.total;
  },
};
