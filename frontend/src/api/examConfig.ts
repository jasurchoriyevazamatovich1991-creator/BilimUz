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

export interface ExamSectionOut {
  id: string;
  test_id: string;
  name: string;
  order_number: number;
  duration: number | null;
  created_at: string;
  updated_at: string;
}

export interface ExamSectionCreateRequest {
  test_id: string;
  name: string;
  order_number: number;
  duration?: number;
}

export interface ExamSectionUpdateRequest {
  name?: string;
  order_number?: number;
  duration?: number | null;
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

export interface QuestionGroupOut {
  id: string;
  test_id: string;
  module_id: string | null;
  title: string;
  stimulus_text: string | null;
  order_number: number;
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
};
