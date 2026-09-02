/**
 * New API wrapper — Question CRUD + granular Option/Media sub-resource
 * endpoints. Every shape verified against real backend
 * app/modules/questions/{schemas,router}.py before writing (10 real
 * endpoints total: 5 Question, 3 Option, 2 Media).
 *
 * NOTE: `options` is submitted NESTED with create() only — there is no
 * bulk-replace endpoint. Post-creation option changes go through
 * addOption/updateOption/deleteOption individually (approved decision
 * 6: the frontend batches these into one "Save" action, but each still
 * becomes its own real API call under the hood — this file does not
 * invent a bulk endpoint that doesn't exist).
 * NOTE: Media has NO update endpoint — only add/delete (verified).
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface OptionOut {
  id: string;
  question_id: string;
  option_text: string;
  is_correct: boolean;
}

export interface OptionCreateRequest {
  option_text: string;
  is_correct: boolean;
}

export interface OptionUpdateRequest {
  option_text?: string;
  is_correct?: boolean;
}

export interface MediaOut {
  id: string;
  question_id: string;
  media_type: string;
  file_url: string;
}

export interface MediaCreateRequest {
  media_type: string;
  file_url: string;
}

export interface QuestionOut {
  id: string;
  test_id: string;
  question_text: string;
  question_type: string;
  difficulty: string;
  score: number;
  explanation: string | null;
  status: string;
  options: OptionOut[];
  media: MediaOut[];
  created_at: string;
  updated_at: string;
}

export interface QuestionListParams {
  page: number;
  per_page: number;
  test_id?: string;
  difficulty?: string;
  status?: string;
  sort?: string;
}

export interface QuestionCreateRequest {
  test_id: string;
  question_text: string;
  question_type: string;
  difficulty?: string;
  score?: number;
  explanation?: string;
  options?: OptionCreateRequest[];
}

export interface QuestionUpdateRequest {
  question_text?: string;
  difficulty?: string;
  score?: number;
  explanation?: string;
  status?: string;
}

export const questionsApi = {
  list: (params: QuestionListParams) => unwrap<PaginatedResponse<QuestionOut>>(httpClient.get("/questions", { params })),

  get: (questionId: string) => unwrap<QuestionOut>(httpClient.get(`/questions/${questionId}`)),

  create: (data: QuestionCreateRequest) => unwrap<QuestionOut>(httpClient.post("/questions", data)),

  update: (questionId: string, data: QuestionUpdateRequest) => unwrap<QuestionOut>(httpClient.patch(`/questions/${questionId}`, data)),

  remove: (questionId: string) => httpClient.delete(`/questions/${questionId}`),

  addOption: (questionId: string, data: OptionCreateRequest) =>
    unwrap<OptionOut>(httpClient.post(`/questions/${questionId}/options`, data)),

  updateOption: (questionId: string, optionId: string, data: OptionUpdateRequest) =>
    unwrap<OptionOut>(httpClient.patch(`/questions/${questionId}/options/${optionId}`, data)),

  deleteOption: (questionId: string, optionId: string) => httpClient.delete(`/questions/${questionId}/options/${optionId}`),

  addMedia: (questionId: string, data: MediaCreateRequest) =>
    unwrap<MediaOut>(httpClient.post(`/questions/${questionId}/media`, data)),

  deleteMedia: (questionId: string, mediaId: string) => httpClient.delete(`/questions/${questionId}/media/${mediaId}`),
};
