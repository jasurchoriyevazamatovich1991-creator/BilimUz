/**
 * Subjects API wrapper. `count()` (Sprint 14) unchanged below — this
 * file is EXTENDED for Sprint 17 (list/get/create/update/remove), not
 * replaced. Every shape verified against real backend
 * app/modules/subjects/{schemas,router}.py before writing.
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface SubjectOut {
  id: string;
  name: string;
  icon: string | null;
  color: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface SubjectListParams {
  page: number;
  per_page: number;
  search?: string;
  status?: string;
  sort?: string;
}

export interface SubjectCreateRequest {
  name: string;
  icon?: string;
  color?: string;
}

export interface SubjectUpdateRequest {
  name?: string;
  icon?: string;
  color?: string;
  status?: string;
}

export const subjectsApi = {
  count: async (): Promise<number> => {
    const result = await unwrap<PaginatedResponse<SubjectOut>>(httpClient.get("/subjects", { params: { per_page: 1 } }));
    return result.meta.total;
  },

  list: (params: SubjectListParams) => unwrap<PaginatedResponse<SubjectOut>>(httpClient.get("/subjects", { params })),

  get: (subjectId: string) => unwrap<SubjectOut>(httpClient.get(`/subjects/${subjectId}`)),

  create: (data: SubjectCreateRequest) => unwrap<SubjectOut>(httpClient.post("/subjects", data)),

  update: (subjectId: string, data: SubjectUpdateRequest) => unwrap<SubjectOut>(httpClient.patch(`/subjects/${subjectId}`, data)),

  remove: (subjectId: string) => httpClient.delete(`/subjects/${subjectId}`),
};
