/**
 * New API wrapper — full CRUD, same style as api/subjects.ts and
 * api/grades.ts. Verified against real backend
 * app/modules/topics/{schemas,router}.py before writing.
 *
 * NOTE: `subject_id` is required on create, but NOT present on
 * TopicUpdateRequest at all (a Topic cannot be moved to a different
 * Subject after creation — matches the backend's own schema exactly,
 * not an oversight).
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface TopicOut {
  id: string;
  subject_id: string;
  grade_id: string | null;
  title: string;
  description: string | null;
  order_number: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface TopicListParams {
  page: number;
  per_page: number;
  search?: string;
  subject_id?: string;
  grade_id?: string;
  status?: string;
  sort?: string;
}

export interface TopicCreateRequest {
  subject_id: string;
  grade_id?: string;
  title: string;
  description?: string;
  order_number?: number;
}

export interface TopicUpdateRequest {
  grade_id?: string;
  title?: string;
  description?: string;
  order_number?: number;
  status?: string;
}

export const topicsApi = {
  list: (params: TopicListParams) => unwrap<PaginatedResponse<TopicOut>>(httpClient.get("/topics", { params })),

  get: (topicId: string) => unwrap<TopicOut>(httpClient.get(`/topics/${topicId}`)),

  create: (data: TopicCreateRequest) => unwrap<TopicOut>(httpClient.post("/topics", data)),

  update: (topicId: string, data: TopicUpdateRequest) => unwrap<TopicOut>(httpClient.patch(`/topics/${topicId}`, data)),

  remove: (topicId: string) => httpClient.delete(`/topics/${topicId}`),
};
