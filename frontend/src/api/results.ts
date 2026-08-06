/**
 * Minimal wrapper for the my-results-count widget (GET /results/me,
 * authenticated — verified against backend/app/modules/results/router.py).
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface ResultOut {
  id: string;
  test_id: string;
  score: number;
  percentage: number;
  is_passed: boolean | null;
}

export const resultsApi = {
  myCount: async (): Promise<number> => {
    const result = await unwrap<PaginatedResponse<ResultOut>>(httpClient.get("/results/me", { params: { per_page: 1 } }));
    return result.meta.total;
  },
};
