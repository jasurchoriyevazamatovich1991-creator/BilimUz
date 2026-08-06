/**
 * Minimal wrapper for the subjects-count widget (GET /subjects, public
 * — verified against backend/app/modules/subjects/router.py).
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface SubjectOut {
  id: string;
  name: string;
}

export const subjectsApi = {
  count: async (): Promise<number> => {
    const result = await unwrap<PaginatedResponse<SubjectOut>>(httpClient.get("/subjects", { params: { per_page: 1 } }));
    return result.meta.total;
  },
};
