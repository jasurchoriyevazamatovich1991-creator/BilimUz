/**
 * Sprint 74 — Admin Exam Configuration API wrapper, for ExamSection/
 * ExamModule/QuestionGroup (Sprint 45-47's generic exam engine
 * foundation, Sprint 51/53's Admin CRUD endpoints). Every shape
 * verified against real backend app/modules/tests/{schemas,router}.py
 * before writing — NOT invented from the hierarchy diagram alone.
 *
 * NOTE: these endpoints require Admin/Super Admin only (NOT Teacher,
 * unlike /tests and /questions) — verified directly in router.py's
 * require_roles() calls. The UI must gate on this more strictly than
 * the existing Tests/Questions pages do.
 *
 * NOTE: ExamSection/ExamModule have NO delete endpoint (verified — only
 * create/list/get/update exist). QuestionGroup has a soft-delete
 * endpoint. Never invented here.
 *
 * NOTE: GET /tests/exam-modules accepts exactly one of section_id/
 * test_id (Sprint 74 addition on the backend side — test_id lists
 * every module across the whole test in one call, avoiding one request
 * per section).
 */
import { httpClient, unwrap } from "./client";
import type { TestOut } from "./tests";

export interface ExamSectionOut {
  id: string;
  test_id: string;
  name: string;
  order_number: number;
  duration: number | null;
  // Task 4 — e.g. "sat_math"; optional so older fixtures stay valid.
  score_component?: string | null;
  // Task 6 — on-screen calculator allowed during this section (default off).
  calculator_enabled?: boolean;
  created_at: string;
  updated_at: string;
}

export interface ExamSectionCreateRequest {
  test_id: string;
  name: string;
  order_number: number;
  duration?: number;
  score_component?: string;
  calculator_enabled?: boolean;
}

export interface ExamSectionUpdateRequest {
  name?: string;
  order_number?: number;
  duration?: number | null;
  score_component?: string | null;
  calculator_enabled?: boolean;
}

/** Task 4 — an immutable, versioned raw-to-scaled table (Admin only). */
export interface ConversionTableOut {
  id: string;
  section_id: string;
  routing_variant: string | null;
  version: number;
  method: "exact" | "linear";
  entries: { raw: string; scaled: string }[];
  is_current: boolean;
  created_by: string | null;
  created_at: string;
}

export interface ConversionTableCreateRequest {
  routing_variant?: string;
  method: "exact" | "linear";
  entries: { raw: string; scaled: string }[];
}

export interface ExamModuleOut {
  id: string;
  section_id: string;
  name: string;
  order_number: number;
  duration: number | null;
  difficulty_tier: string | null;
  routing_group: string | null;
  routing_variant: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExamModuleCreateRequest {
  section_id: string;
  name: string;
  order_number: number;
  duration?: number;
  difficulty_tier?: string;
  routing_group?: string;
  routing_variant?: string;
}

export interface ExamModuleUpdateRequest {
  name?: string;
  order_number?: number;
  duration?: number | null;
  difficulty_tier?: string | null;
  routing_group?: string | null;
  routing_variant?: string | null;
}

/** Task 3 — media attached to a question group (e.g. IELTS Listening audio). */
export interface QuestionGroupMediaOut {
  id: string;
  group_id: string;
  upload_id: string;
  media_type: string;
  created_at: string;
}

export interface QuestionGroupOut {
  id: string;
  test_id: string;
  module_id: string | null;
  title: string;
  stimulus_text: string | null;
  order_number: number;
  // Task 3 — optional so pre-Task-3 fixtures stay valid.
  media?: QuestionGroupMediaOut[];
  created_at: string;
  updated_at: string;
}

export interface QuestionGroupCreateRequest {
  test_id: string;
  module_id?: string;
  title: string;
  stimulus_text?: string;
  order_number: number;
}

export interface QuestionGroupUpdateRequest {
  module_id?: string | null;
  title?: string;
  stimulus_text?: string | null;
  order_number?: number;
}

export const examSectionsApi = {
  list: (testId: string) => unwrap<ExamSectionOut[]>(httpClient.get("/tests/exam-sections", { params: { test_id: testId } })),

  get: (sectionId: string) => unwrap<ExamSectionOut>(httpClient.get(`/tests/exam-sections/${sectionId}`)),

  create: (data: ExamSectionCreateRequest) => unwrap<ExamSectionOut>(httpClient.post("/tests/exam-sections", data)),

  update: (sectionId: string, data: ExamSectionUpdateRequest) =>
    unwrap<ExamSectionOut>(httpClient.patch(`/tests/exam-sections/${sectionId}`, data)),
};

// Task 4 — exam-specific scaled scoring configuration (Admin/Super Admin).
export const scoringApi = {
  setProfile: (testId: string, scoringProfile: "ielts" | "sat" | "gre" | null) =>
    unwrap<TestOut>(httpClient.put(`/tests/${testId}/scoring-profile`, { scoring_profile: scoringProfile })),

  listTables: (sectionId: string) =>
    unwrap<ConversionTableOut[]>(httpClient.get(`/tests/exam-sections/${sectionId}/conversion-tables`)),

  publishTable: (sectionId: string, data: ConversionTableCreateRequest) =>
    unwrap<ConversionTableOut>(httpClient.post(`/tests/exam-sections/${sectionId}/conversion-tables`, data)),
};

export const examModulesApi = {
  /** Every module across a whole test, in one call — Sprint 74 backend addition. */
  listForTest: (testId: string) => unwrap<ExamModuleOut[]>(httpClient.get("/tests/exam-modules", { params: { test_id: testId } })),

  listForSection: (sectionId: string) =>
    unwrap<ExamModuleOut[]>(httpClient.get("/tests/exam-modules", { params: { section_id: sectionId } })),

  get: (moduleId: string) => unwrap<ExamModuleOut>(httpClient.get(`/tests/exam-modules/${moduleId}`)),

  create: (data: ExamModuleCreateRequest) => unwrap<ExamModuleOut>(httpClient.post("/tests/exam-modules", data)),

  update: (moduleId: string, data: ExamModuleUpdateRequest) =>
    unwrap<ExamModuleOut>(httpClient.patch(`/tests/exam-modules/${moduleId}`, data)),
};

export const questionGroupsApi = {
  list: (testId: string) => unwrap<QuestionGroupOut[]>(httpClient.get("/tests/question-groups", { params: { test_id: testId } })),

  get: (groupId: string) => unwrap<QuestionGroupOut>(httpClient.get(`/tests/question-groups/${groupId}`)),

  create: (data: QuestionGroupCreateRequest) => unwrap<QuestionGroupOut>(httpClient.post("/tests/question-groups", data)),

  update: (groupId: string, data: QuestionGroupUpdateRequest) =>
    unwrap<QuestionGroupOut>(httpClient.patch(`/tests/question-groups/${groupId}`, data)),

  remove: (groupId: string) => httpClient.delete(`/tests/question-groups/${groupId}`),

  // Task 3 — media_type is decided by the backend from the upload itself.
  addMedia: (groupId: string, uploadId: string) =>
    unwrap<QuestionGroupMediaOut>(httpClient.post(`/tests/question-groups/${groupId}/media`, { upload_id: uploadId })),

  removeMedia: (groupId: string, mediaId: string) => httpClient.delete(`/tests/question-groups/${groupId}/media/${mediaId}`),
};

/**
 * Sprint 75 completion — Adaptive Routing Rule Admin CRUD. Persisted
 * configuration for PerformanceThresholdRoutingStrategy. Same Admin/
 * Super Admin-only RBAC as ExamSection/ExamModule/QuestionGroup above
 * (verified in backend router.py's require_roles calls). No GET-by-id
 * endpoint exists on the backend — only list (by test_id), create,
 * patch, delete — never invented here.
 */
export interface RoutingThresholdRuleOut {
  id: string;
  test_id: string;
  routing_group: string;
  min_ratio: number;
  variant: string;
  created_at: string;
  updated_at: string;
}

export interface RoutingThresholdRuleCreateRequest {
  test_id: string;
  routing_group: string;
  min_ratio: number;
  variant: string;
}

export interface RoutingThresholdRuleUpdateRequest {
  routing_group?: string;
  min_ratio?: number;
  variant?: string;
}

export const routingThresholdRulesApi = {
  list: (testId: string) =>
    unwrap<RoutingThresholdRuleOut[]>(httpClient.get("/tests/routing-threshold-rules", { params: { test_id: testId } })),

  create: (data: RoutingThresholdRuleCreateRequest) =>
    unwrap<RoutingThresholdRuleOut>(httpClient.post("/tests/routing-threshold-rules", data)),

  update: (ruleId: string, data: RoutingThresholdRuleUpdateRequest) =>
    unwrap<RoutingThresholdRuleOut>(httpClient.patch(`/tests/routing-threshold-rules/${ruleId}`, data)),

  remove: (ruleId: string) => httpClient.delete(`/tests/routing-threshold-rules/${ruleId}`),
};
