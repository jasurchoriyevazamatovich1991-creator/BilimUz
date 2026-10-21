/**
 * Tests API wrapper. `publishedCount()` (Sprint 14) unchanged below —
 * extended, not replaced. Every shape verified against real backend
 * app/modules/tests/{schemas,router}.py before writing.
 *
 * NOTE: subject_id/grade_id/topic_id are ALL optional and remain
 * editable via update() (unlike Topics'/Lessons' immutable-parent
 * shape) — verified directly, not assumed from those precedents.
 * NOTE: only `publish()` exists as a status-transition action — there
 * is NO archive endpoint despite ALLOWED_STATUS_TRANSITIONS mentioning
 * an "archived" state in the backend's own constants.py (approved
 * decision 2: no Archive UI is built here).
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface TestOut {
  id: string;
  subject_id: string | null;
  grade_id: string | null;
  topic_id: string | null;
  title: string;
  description: string | null;
  difficulty: string;
  duration: number;
  question_count: number;
  passing_score: number | null;
  shuffle_questions: boolean;
  shuffle_answers: boolean;
  status: string;
  // Mock Test Entitlements feature. Optional here (not `boolean`) so
  // the many existing TestOut literals across this codebase's test
  // files don't all need updating — a real API response always
  // includes it (backend TestOut.is_mock_test is non-optional), this
  // is purely a frontend-type convenience. Falsy/undefined reads the
  // same as `false` everywhere this is checked.
  is_mock_test?: boolean;
  // Task 4 — 'ielts' | 'sat' | 'gre' | null (plain percentage scoring).
  scoring_profile?: "ielts" | "sat" | "gre" | null;
  created_at: string;
  updated_at: string;
}

export interface TestListParams {
  page: number;
  per_page: number;
  search?: string;
  subject_id?: string;
  grade_id?: string;
  topic_id?: string;
  difficulty?: string;
  status?: string;
  sort?: string;
}

export interface TestCreateRequest {
  subject_id?: string;
  grade_id?: string;
  topic_id?: string;
  title: string;
  description?: string;
  difficulty?: string;
  duration?: number;
  passing_score?: number;
  shuffle_questions?: boolean;
  shuffle_answers?: boolean;
  is_mock_test?: boolean;
}

export interface TestUpdateRequest {
  subject_id?: string;
  grade_id?: string;
  topic_id?: string;
  title?: string;
  description?: string;
  difficulty?: string;
  duration?: number;
  passing_score?: number;
  shuffle_questions?: boolean;
  shuffle_answers?: boolean;
  is_mock_test?: boolean;
}

export const testsApi = {
  publishedCount: async (): Promise<number> => {
    const result = await unwrap<PaginatedResponse<TestOut>>(
      httpClient.get("/tests", { params: { per_page: 1, status: "published" } }),
    );
    return result.meta.total;
  },

  list: (params: TestListParams) => unwrap<PaginatedResponse<TestOut>>(httpClient.get("/tests", { params })),

  get: (testId: string) => unwrap<TestOut>(httpClient.get(`/tests/${testId}`)),

  create: (data: TestCreateRequest) => unwrap<TestOut>(httpClient.post("/tests", data)),

  update: (testId: string, data: TestUpdateRequest) => unwrap<TestOut>(httpClient.patch(`/tests/${testId}`, data)),

  publish: (testId: string) => unwrap<TestOut>(httpClient.post(`/tests/${testId}/publish`, {})),

  remove: (testId: string) => httpClient.delete(`/tests/${testId}`),
};
