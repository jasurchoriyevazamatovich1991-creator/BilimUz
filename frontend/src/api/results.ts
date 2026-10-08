/**
 * Results API wrapper. `myCount()` (Sprint 14) unchanged below —
 * extended, not replaced. Paths verified directly against real backend
 * app/modules/results/router.py: POST /results, GET /results/me,
 * GET /results/{id}.
 *
 * Sprint 37: GET /results/{id} now returns ResultDetailOut — every
 * ResultOut field plus real analysis (counts, time spent, question
 * review) derived from persisted Answer/TestAttempt/Question data.
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface ResultOut {
  id: string;
  attempt_id: string;
  user_id: string;
  test_id: string;
  score: number;
  percentage: number;
  is_passed: boolean | null;
  status: string;
  created_at: string;
}

export interface ResultListParams {
  page: number;
  per_page: number;
  test_id?: string;
}

// --- Sprint 37: Result Analysis ---

export interface OptionReviewOut {
  id: string;
  option_text: string;
  is_correct: boolean;
}

export interface QuestionReviewOut {
  question_id: string;
  question_text: string;
  question_type: string;
  explanation: string | null;
  options: OptionReviewOut[];
  selected_option: string | null;
  selected_options: string[] | null;
  /** null means unanswered — mirrors the backend's own Answer.is_correct convention. */
  is_correct: boolean | null;
  /** Sprint 70 — the student's submitted free-text answer for
   * short_answer/essay questions. null both when unanswered and for
   * choice-based question types. short_answer/essay are never
   * auto-graded, so is_correct stays null for them even when answered —
   * check this field to tell "answered, not auto-graded" apart from
   * "unanswered". */
  text_answer: string | null;
  /** Sprint 80 — additive, all optional/default null (mirrors
   * attempts.ts's identical Sprint 77 QuestionForAttemptOut.group_id/
   * group_title/stimulus_text fields exactly, including staying
   * optional here so every pre-Sprint-80 test fixture that omits them
   * entirely keeps compiling, same as that file's own convention).
   * null/absent for every ungrouped question (all pre-Sprint-80
   * results, unchanged) and also null when the referenced group has
   * been soft-deleted. */
  group_id?: string | null;
  group_title?: string | null;
  stimulus_text?: string | null;
}

/** Sprint 55 (backend) / Sprint 73 — RS-FE-1 (frontend): read-only
 * exposure of a modular test's per-section score. Empty for every
 * non-modular test (the vast majority) — `sections` is always `[]` in
 * that case, never missing. `name`/`order_number` added in Sprint 73;
 * nullable because a ResultSection can theoretically outlive its
 * ExamSection row (see backend ResultSectionOut docstring). */
export interface ResultSectionOut {
  id: string;
  section_id: string;
  name: string | null;
  order_number: number | null;
  raw_score: number | null;
  scaled_score: number | null;
}

export interface ResultDetailOut extends ResultOut {
  total_questions: number;
  correct_answers: number;
  incorrect_answers: number;
  unanswered: number;
  /** null only if the underlying attempt has no finish_time. */
  time_spent_seconds: number | null;
  questions: QuestionReviewOut[];
  /** Already ordered by ExamSection.order_number by the backend. */
  sections: ResultSectionOut[];
}

export const resultsApi = {
  myCount: async (): Promise<number> => {
    const result = await unwrap<PaginatedResponse<ResultOut>>(httpClient.get("/results/me", { params: { per_page: 1 } }));
    return result.meta.total;
  },

  /** Sprint 34 — the full paginated list, reusing the exact same
   * GET /results/me endpoint myCount() above already calls (just
   * without pinning per_page to 1). */
  list: (params: ResultListParams) => unwrap<PaginatedResponse<ResultOut>>(httpClient.get("/results/me", { params })),

  /** Idempotent on the backend (returns the existing Result if one
   * already exists for this attempt_id) — safe to call more than once. */
  create: (attemptId: string) => unwrap<ResultOut>(httpClient.post("/results", { attempt_id: attemptId })),

  get: (resultId: string) => unwrap<ResultDetailOut>(httpClient.get(`/results/${resultId}`)),
};
