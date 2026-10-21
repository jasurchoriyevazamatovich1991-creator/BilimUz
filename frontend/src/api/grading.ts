/**
 * Task 5 — manual grading API (IELTS Writing/Speaking, GRE AWA).
 * Shapes mirror backend app/modules/grading/schemas.py. Requests carry
 * only grader-editable fields; grader, status, rubric and revision data
 * are always set by the server.
 */
import { httpClient, unwrap } from "./client";

export type ManualComponent = "ielts_writing" | "ielts_speaking" | "gre_analytical_writing";
export type QueueStatus = "pending" | "draft" | "finalized";

export interface RubricCriterion {
  key: string;
  label: string;
  min: string;
  max: string;
  step: string;
  weight: string;
}

export interface RubricOut {
  id: string;
  score_component: ManualComponent;
  version: number;
  name: string;
  criteria: RubricCriterion[];
  rounding: "half_up" | "floor";
  instructions: string | null;
  is_validated: boolean;
  is_current: boolean;
  created_at: string;
}

export interface RubricCreateRequest {
  score_component: ManualComponent;
  name: string;
  criteria: { key: string; label: string; min: string; max: string; step: string; weight: string }[];
  rounding: "half_up" | "floor";
  instructions?: string;
  is_validated: boolean;
}

export interface ReviewOut {
  id: string;
  status: "draft" | "finalized" | "superseded";
  rubric_id: string;
  rubric_version: number | null;
  grader_id: string;
  criterion_scores: Record<string, string>;
  criterion_total: number | null;
  reported_score: number | null;
  is_provisional: boolean;
  feedback: string | null;
  internal_notes: string | null;
  revision_number: number;
  supersedes_id: string | null;
  revision_reason: string | null;
  finalized_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface QueueItemOut {
  attempt_id: string;
  question_id: string;
  test_id: string;
  test_title: string;
  section_name: string;
  score_component: ManualComponent;
  status: QueueStatus;
  finished_at: string | null;
  reported_score: number | null;
}

export interface QueuePage {
  items: QueueItemOut[];
  total: number;
  page: number;
  per_page: number;
}

export interface SubmissionDetailOut {
  attempt_id: string;
  question_id: string;
  test_title: string;
  section_name: string;
  score_component: ManualComponent;
  question_text: string;
  question_type: string;
  response_text: string | null;
  status: QueueStatus;
  rubric: RubricOut | null;
  reviews: ReviewOut[];
  // Task 6 — a recorded Speaking response exists (optional for older fixtures).
  has_audio?: boolean;
}

export interface DraftSaveRequest {
  criterion_scores: Record<string, string>;
  feedback?: string | null;
  internal_notes?: string | null;
}

const item = (attemptId: string, questionId: string) => `/grading/submissions/${attemptId}/${questionId}`;

export const gradingApi = {
  listRubrics: (component?: ManualComponent) =>
    unwrap<RubricOut[]>(httpClient.get("/grading/rubrics", { params: component ? { score_component: component } : {} })),
  createRubric: (data: RubricCreateRequest) => unwrap<RubricOut>(httpClient.post("/grading/rubrics", data)),

  listQueue: (params: { status?: QueueStatus; page?: number; per_page?: number }) =>
    unwrap<QueuePage>(httpClient.get("/grading/submissions", { params })),
  getSubmission: (attemptId: string, questionId: string) => unwrap<SubmissionDetailOut>(httpClient.get(item(attemptId, questionId))),
  saveDraft: (attemptId: string, questionId: string, data: DraftSaveRequest) =>
    unwrap<ReviewOut>(httpClient.put(`${item(attemptId, questionId)}/draft`, data)),
  finalize: (attemptId: string, questionId: string) => unwrap<ReviewOut>(httpClient.post(`${item(attemptId, questionId)}/finalize`)),
  revise: (attemptId: string, questionId: string, reason: string) =>
    unwrap<ReviewOut>(httpClient.post(`${item(attemptId, questionId)}/revise`, { reason })),
  // Task 6 — the student's Speaking recording, streamed through the
  // permission-checked grading endpoint (GRADE_SUBMISSIONS).
  getAudio: async (attemptId: string, questionId: string): Promise<Blob> => {
    const response = await httpClient.get<Blob>(`${item(attemptId, questionId)}/audio`, { responseType: "blob" });
    return response.data;
  },
};
