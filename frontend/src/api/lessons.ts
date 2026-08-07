/**
 * Lessons API wrapper. `count()` (Sprint 14) unchanged below — this
 * file is EXTENDED for Sprint 18 (list/get/create/update/remove), not
 * replaced. Every shape verified against real backend
 * app/modules/lessons/{schemas,router}.py before writing.
 *
 * NOTE: `topic_id` is required on create, but NOT present on
 * LessonUpdateRequest at all (a Lesson cannot be moved to a different
 * Topic after creation — matches the backend's own schema exactly,
 * same shape as topics/subject_id).
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface LessonOut {
  id: string;
  topic_id: string;
  title: string;
  video: string | null;
  pdf: string | null;
  content: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface LessonListParams {
  page: number;
  per_page: number;
  search?: string;
  topic_id?: string;
  status?: string;
  sort?: string;
}

export interface LessonCreateRequest {
  topic_id: string;
  title: string;
  video?: string;
  pdf?: string;
  content?: string;
}

export interface LessonUpdateRequest {
  title?: string;
  video?: string;
  pdf?: string;
  content?: string;
  status?: string;
}

export const lessonsApi = {
  count: async (): Promise<number> => {
    const result = await unwrap<PaginatedResponse<LessonOut>>(httpClient.get("/lessons", { params: { per_page: 1 } }));
    return result.meta.total;
  },

  list: (params: LessonListParams) => unwrap<PaginatedResponse<LessonOut>>(httpClient.get("/lessons", { params })),

  get: (lessonId: string) => unwrap<LessonOut>(httpClient.get(`/lessons/${lessonId}`)),

  create: (data: LessonCreateRequest) => unwrap<LessonOut>(httpClient.post("/lessons", data)),

  update: (lessonId: string, data: LessonUpdateRequest) => unwrap<LessonOut>(httpClient.patch(`/lessons/${lessonId}`, data)),

  remove: (lessonId: string) => httpClient.delete(`/lessons/${lessonId}`),
};
