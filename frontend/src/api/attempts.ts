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
  // Sprint 67 (C2) — additive, mirrors the backend's own
  // AnsweredQuestionState.selected_options (schemas.py, Sprint 30) and
  // the naming convention already used by ResultPage's
  // QuestionReviewOut (api/results.ts). Populated for multiple_choice
  // questions only; null for single_choice/true_false, exactly like
  // selected_option is null for an unanswered/non-multiple_choice
  // question in the other direction.
  selected_options: string[] | null;
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

  // Sprint 67 (C2) — a single_choice/true_false answer still sends only
  // selected_option, exactly as before; a multiple_choice answer sends
  // only selected_options, never a fake/placeholder selected_option.
  // Same existing PATCH /attempts/{id}/answer endpoint — the backend
  // request schema (SaveAnswerRequest) already accepts both fields
  // (Sprint 30), this was purely a frontend gap.
  saveAnswer: (
    attemptId: string,
    questionId: string,
    answer: { selectedOption: string | null } | { selectedOptions: string[] },
  ) =>
    httpClient.patch(`/attempts/${attemptId}/answer`, {
      question_id: questionId,
      ...("selectedOptions" in answer
        ? { selected_options: answer.selectedOptions }
        : { selected_option: answer.selectedOption }),
    }),

  submit: (attemptId: string) => unwrap<SubmitResultOut>(httpClient.post(`/attempts/${attemptId}/submit`)),

  getResult: (attemptId: string) => unwrap<SubmitResultOut>(httpClient.get(`/attempts/${attemptId}/result`)),
};
