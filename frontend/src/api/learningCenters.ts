/**
 * Learning Centers API wrapper. `count()` (Sprint 14) unchanged below —
 * extended, not replaced. Verified against real backend
 * app/modules/learning_centers/{schemas,router}.py before writing.
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface LearningCenterOut {
  id: string;
  name: string;
  owner_name: string | null;
  phone: string | null;
  region: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface LearningCenterListParams {
  page: number;
  per_page: number;
  search?: string;
  region?: string;
  status?: string;
  sort?: string;
}

export interface LearningCenterCreateRequest {
  name: string;
  owner_name?: string;
  phone?: string;
  region?: string;
}

export interface LearningCenterUpdateRequest {
  name?: string;
  owner_name?: string;
  phone?: string;
  region?: string;
  status?: string;
}

export const learningCentersApi = {
  count: async (): Promise<number> => {
    const result = await unwrap<PaginatedResponse<LearningCenterOut>>(
      httpClient.get("/learning-centers", { params: { per_page: 1 } }),
    );
    return result.meta.total;
  },

  list: (params: LearningCenterListParams) =>
    unwrap<PaginatedResponse<LearningCenterOut>>(httpClient.get("/learning-centers", { params })),

  get: (centerId: string) => unwrap<LearningCenterOut>(httpClient.get(`/learning-centers/${centerId}`)),

  create: (data: LearningCenterCreateRequest) => unwrap<LearningCenterOut>(httpClient.post("/learning-centers", data)),

  update: (centerId: string, data: LearningCenterUpdateRequest) =>
    unwrap<LearningCenterOut>(httpClient.patch(`/learning-centers/${centerId}`, data)),

  remove: (centerId: string) => httpClient.delete(`/learning-centers/${centerId}`),
};
