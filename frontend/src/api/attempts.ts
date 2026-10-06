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
  // Sprint 68 — additive. Backend field added this sprint (see backend
  // AnsweredQuestionState docstring) specifically so a previously typed
  // short_answer/essay answer can be resumed. null unless this question
  // is short_answer/essay and has a saved answer.
  text_answer: string | null;
}

export interface AttemptDetailOut extends AttemptOut {
  questions: QuestionForAttemptOut[];
  answered: AnsweredQuestionState[];
  // Sprint 76 — additive, optional here (backend always sends both, but
  // marking them optional on the frontend type keeps every pre-existing
  // test fixture in this file's test suite — built before these fields
  // existed — valid without touching them). null/undefined for a
  // non-modular attempt (the backend sends null) — the only new signal
  // this page needs to tell "is this a modular exam".
  module_id?: string | null;
  // The active module's real, per-attempt deadline
  // (AttemptModuleProgress.expires_at) — independent of the whole-
  // attempt `expires_at` above. null when module_id is null, or when
  // the active module has no duration set.
  module_expires_at?: string | null;
}

// Sprint 76 — student-scoped module/section metadata (Sprint A,
// post-75). Deliberately excludes difficulty_tier/routing_group/
// routing_variant (admin-only routing configuration, see
// api/examConfig.ts's ExamModuleOut) — a student never needs or sees
// adaptive-routing internals, only what to call this module/section.
export interface ModuleForAttemptOut {
  id: string;
  name: string;
  order_number: number;
  duration: number | null;
  section_id: string;
  section_name: string;
  section_order_number: number;
}

// Sprint 76 — response of POST /attempts/{id}/modules/{module_id}/submit
// (backend SubmitModuleResultOut, Sprint 50). result is populated only
// when completed is true, mirroring SubmitResultOut's own rule.
export interface SubmitModuleResultOut {
  completed: boolean;
  next_module_id: string | null;
  result: SubmitResultOut | null;
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
  //
  // Sprint 68 — additive third variant: a short_answer/essay answer
  // sends only text_answer, never selected_option or selected_options.
  // The backend request schema has accepted text_answer since Sprint
  // 66 (SaveAnswerRequest.text_answer); this too was purely a frontend
  // gap.
  saveAnswer: (
    attemptId: string,
    questionId: string,
    answer: { selectedOption: string | null } | { selectedOptions: string[] } | { textAnswer: string },
  ) =>
    httpClient.patch(`/attempts/${attemptId}/answer`, {
      question_id: questionId,
      ...("selectedOptions" in answer
        ? { selected_options: answer.selectedOptions }
        : "textAnswer" in answer
          ? { text_answer: answer.textAnswer }
          : { selected_option: answer.selectedOption }),
    }),

  submit: (attemptId: string) => unwrap<SubmitResultOut>(httpClient.post(`/attempts/${attemptId}/submit`)),

  getResult: (attemptId: string) => unwrap<SubmitResultOut>(httpClient.get(`/attempts/${attemptId}/result`)),

  // Sprint 76 — student-scoped module/section name/order lookup, for
  // the module navigator. Same backend endpoint Sprint A added
  // (GET /attempts/{id}/modules/{module_id}); this is its first
  // frontend consumer.
  getModule: (attemptId: string, moduleId: string) =>
    unwrap<ModuleForAttemptOut>(httpClient.get(`/attempts/${attemptId}/modules/${moduleId}`)),

  // Sprint 76 — integrates the existing (Sprint 50) module-submit
  // endpoint; no new backend endpoint was created for this.
  submitModule: (attemptId: string, moduleId: string) =>
    unwrap<SubmitModuleResultOut>(httpClient.post(`/attempts/${attemptId}/modules/${moduleId}/submit`)),
};
