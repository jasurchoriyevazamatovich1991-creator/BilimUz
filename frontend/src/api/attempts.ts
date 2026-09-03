/**
 * Attempts API wrapper. `myCount()` (Sprint 14) unchanged below —
 * extended, not replaced. Every path/shape verified against real
 * backend app/modules/attempts/{schemas,router}.py before writing —
 * paths confirmed directly (not assumed): POST /attempts/start,
 * GET /attempts/me, GET /attempts/{id}, PATCH /attempts/{id}/answer,
 * POST /attempts/{id}/submit, GET /attempts/{id}/result.
 *
 * NOTE: is_correct is NEVER present anywhere in this file's types —
 * the backend's QuestionForAttemptOut/OptionForAttemptOut deliberately
 * exclude it. Not omitted by accident.
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface AttemptOut {
  id: string;
  test_id: string;
  status: string;
  start_time: string;
  expires_at: string | null;
  finish_time: string | null;
}

export interface OptionForAttemptOut {
  id: string;
  option_text: string;
}

export interface QuestionForAttemptOut {
  id: string;
  question_text: string;
  question_type: string;
  score: number;
  options: OptionForAttemptOut[];
}

export interface AnsweredQuestionState {
  question_id: string;
  is_answered: boolean;
  selected_option: string | null;
}

export interface AttemptDetailOut extends AttemptOut {
  questions: QuestionForAttemptOut[];
  answered: AnsweredQuestionState[];
}

export interface SubmitResultOut {
  attempt_id: string;
  score: number;
  percentage: number;
  is_passed: boolean | null;
  total_questions: number;
  correct_count: number;
  status: string;
}

export interface AttemptListParams {
  page: number;
  per_page: number;
  test_id?: string;
  status?: string;
}

export const attemptsApi = {
  myCount: async (): Promise<number> => {
    const result = await unwrap<PaginatedResponse<AttemptOut>>(httpClient.get("/attempts/me", { params: { per_page: 1 } }));
    return result.meta.total;
  },

  listMine: (params: AttemptListParams) => unwrap<PaginatedResponse<AttemptOut>>(httpClient.get("/attempts/me", { params })),

  start: (testId: string) => unwrap<AttemptOut>(httpClient.post("/attempts/start", { test_id: testId })),

  get: (attemptId: string) => unwrap<AttemptDetailOut>(httpClient.get(`/attempts/${attemptId}`)),

  saveAnswer: (attemptId: string, questionId: string, selectedOption: string | null) =>
    httpClient.patch(`/attempts/${attemptId}/answer`, { question_id: questionId, selected_option: selectedOption }),

  submit: (attemptId: string) => unwrap<SubmitResultOut>(httpClient.post(`/attempts/${attemptId}/submit`)),

  getResult: (attemptId: string) => unwrap<SubmitResultOut>(httpClient.get(`/attempts/${attemptId}/result`)),
};
