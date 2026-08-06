/**
 * New API wrapper — GET /roles, Admin/Super Admin only (verified
 * against backend/app/modules/roles/router.py before writing this
 * file). Only 8 roles exist total (seeded, see
 * database/schema/schema_v2.sql) — a single per_page=100 call covers
 * all of them, no pagination UI needed for this lookup use case.
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface RoleOut {
  id: string;
  name: string;
  description: string | null;
  status: string;
}

export const rolesApi = {
  list: async (): Promise<RoleOut[]> => {
    const result = await unwrap<PaginatedResponse<RoleOut>>(httpClient.get("/roles", { params: { per_page: 100 } }));
    return result.items;
  },
};
