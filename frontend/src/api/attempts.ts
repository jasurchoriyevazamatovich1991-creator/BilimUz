/**
 * Minimal wrapper for the my-attempts-count widget (GET /attempts/me,
 * authenticated — verified against backend/app/modules/attempts/router.py).
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface AttemptOut {
  id: string;
  test_id: string;
  status: string;
}

export const attemptsApi = {
  myCount: async (): Promise<number> => {
    const result = await unwrap<PaginatedResponse<AttemptOut>>(httpClient.get("/attempts/me", { params: { per_page: 1 } }));
    return result.meta.total;
  },
};
