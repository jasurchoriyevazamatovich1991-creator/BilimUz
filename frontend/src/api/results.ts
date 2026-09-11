/**
 * Results API wrapper. `myCount()` (Sprint 14) unchanged below —
 * extended, not replaced. Paths verified directly against real backend
 * app/modules/results/router.py: POST /results, GET /results/me,
 * GET /results/{id}.
 *
 * NOTE: ResultOut has no per-question correct/wrong breakdown — the
 * backend schema simply doesn't have one (BACKEND GAP, not omitted by
 * mistake). No "review your answers" field is invented here.
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface ResultOut {
  id: string;
  attempt_id: string;
  user_id: string;
  test_id: string;
  score: number;
  percentage: number;
  is_passed: boolean | null;
  status: string;
  created_at: string;
}

export interface ResultListParams {
  page: number;
  per_page: number;
  test_id?: string;
}

export const resultsApi = {
  myCount: async (): Promise<number> => {
    const result = await unwrap<PaginatedResponse<ResultOut>>(httpClient.get("/results/me", { params: { per_page: 1 } }));
    return result.meta.total;
  },

  /** Sprint 34 — the full paginated list, reusing the exact same
   * GET /results/me endpoint myCount() above already calls (just
   * without pinning per_page to 1). */
  list: (params: ResultListParams) => unwrap<PaginatedResponse<ResultOut>>(httpClient.get("/results/me", { params })),

  /** Idempotent on the backend (returns the existing Result if one
   * already exists for this attempt_id) — safe to call more than once. */
  create: (attemptId: string) => unwrap<ResultOut>(httpClient.post("/results", { attempt_id: attemptId })),

  get: (resultId: string) => unwrap<ResultOut>(httpClient.get(`/results/${resultId}`)),
};
