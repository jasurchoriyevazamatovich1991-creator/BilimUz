/**
 * New API wrapper — full CRUD, exact same style/architecture as
 * api/subjects.ts (approved decision). Verified against real backend
 * app/modules/grades/{schemas,router}.py before writing.
 *
 * NOTE: `update()` only ever sends `status` — `GradeUpdateRequest` on
 * the backend deliberately has no `name` field (renaming in place
 * could silently break anything referencing the old name elsewhere,
 * per the backend's own docstring). `GradeUpdateRequest` here mirrors
 * that exactly, not a smaller version of SubjectUpdateRequest.
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface GradeOut {
  id: string;
  name: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface GradeListParams {
  page: number;
  per_page: number;
  search?: string;
  status?: string;
  sort?: string;
}

export interface GradeCreateRequest {
  name: string;
}

export interface GradeUpdateRequest {
  status?: string;
}

export const gradesApi = {
  list: (params: GradeListParams) => unwrap<PaginatedResponse<GradeOut>>(httpClient.get("/grades", { params })),

  get: (gradeId: string) => unwrap<GradeOut>(httpClient.get(`/grades/${gradeId}`)),

  create: (data: GradeCreateRequest) => unwrap<GradeOut>(httpClient.post("/grades", data)),

  update: (gradeId: string, data: GradeUpdateRequest) => unwrap<GradeOut>(httpClient.patch(`/grades/${gradeId}`, data)),

  remove: (gradeId: string) => httpClient.delete(`/grades/${gradeId}`),
};
