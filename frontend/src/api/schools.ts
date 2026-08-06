/** Minimal wrapper for the schools-count widget (GET /schools, public
 * — verified against backend/app/modules/schools/router.py). */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface SchoolOut {
  id: string;
  name: string;
}

export const schoolsApi = {
  count: async (): Promise<number> => {
    const result = await unwrap<PaginatedResponse<SchoolOut>>(httpClient.get("/schools", { params: { per_page: 1 } }));
    return result.meta.total;
  },
};
