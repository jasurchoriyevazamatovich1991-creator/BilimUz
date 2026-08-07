/**
 * Schools API wrapper. `count()` (Sprint 14) is unchanged below — this
 * file is EXTENDED for Sprint 16 (list/get/create/update/remove), not
 * replaced. Every shape verified against real backend
 * app/modules/schools/{schemas,router}.py before writing. Unlike
 * Sprint 15's Users module, Schools has full CRUD on the backend
 * (verified — GET/GET/POST/PATCH/DELETE all exist).
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface SchoolOut {
  id: string;
  name: string;
  region: string | null;
  district: string | null;
  address: string | null;
  phone: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface SchoolListParams {
  page: number;
  per_page: number;
  search?: string;
  region?: string;
  district?: string;
  status?: string;
  sort?: string;
}

export interface SchoolCreateRequest {
  name: string;
  region?: string;
  district?: string;
  address?: string;
  phone?: string;
}

export interface SchoolUpdateRequest {
  name?: string;
  region?: string;
  district?: string;
  address?: string;
  phone?: string;
  status?: string;
}

export const schoolsApi = {
  count: async (): Promise<number> => {
    const result = await unwrap<PaginatedResponse<SchoolOut>>(httpClient.get("/schools", { params: { per_page: 1 } }));
    return result.meta.total;
  },

  list: (params: SchoolListParams) => unwrap<PaginatedResponse<SchoolOut>>(httpClient.get("/schools", { params })),

  get: (schoolId: string) => unwrap<SchoolOut>(httpClient.get(`/schools/${schoolId}`)),

  create: (data: SchoolCreateRequest) => unwrap<SchoolOut>(httpClient.post("/schools", data)),

  update: (schoolId: string, data: SchoolUpdateRequest) => unwrap<SchoolOut>(httpClient.patch(`/schools/${schoolId}`, data)),

  remove: (schoolId: string) => httpClient.delete(`/schools/${schoolId}`),
};
