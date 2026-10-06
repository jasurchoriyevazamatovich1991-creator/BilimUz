/**
 * Sprint 74 — Admin Exam Configuration data hooks. Same shape as
 * hooks/useTests.ts / hooks/useQuestions.ts (React Query + toast-on-
 * error + cache invalidation on mutation success).
 */
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import {
  examModulesApi,
  examSectionsApi,
  questionGroupsApi,
  routingThresholdRulesApi,
  type ExamModuleCreateRequest,
  type ExamModuleUpdateRequest,
  type ExamSectionCreateRequest,
  type ExamSectionUpdateRequest,
  type QuestionGroupCreateRequest,
  type QuestionGroupUpdateRequest,
  type RoutingThresholdRuleCreateRequest,
  type RoutingThresholdRuleUpdateRequest,
} from "@/api/examConfig";
import { useToastStore } from "@/store/toastStore";
import { ApiError } from "@/api/client";

function useToastOnQueryError(query: UseQueryResult<unknown, unknown>) {
  const addToast = useToastStore((s) => s.addToast);
  useEffect(() => {
    if (query.isError) {
      addToast(query.error instanceof ApiError ? query.error.message : "Ma'lumot yuklanmadi");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.isError, query.error]);
}

// --- ExamSection ---

export function useExamSectionsList(testId: string | undefined) {
  const query = useQuery({
    queryKey: ["examSections", "list", testId],
    queryFn: () => examSectionsApi.list(testId as string),
    enabled: !!testId,
  });
  useToastOnQueryError(query);
  return query;
}

export function useCreateExamSection() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: ExamSectionCreateRequest) => examSectionsApi.create(data),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ["examSections", "list", created.test_id] });
      addToast("Bo'lim yaratildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yaratib bo'lmadi"),
  });
}

export function useUpdateExamSection(testId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: ({ sectionId, data }: { sectionId: string; data: ExamSectionUpdateRequest }) =>
      examSectionsApi.update(sectionId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["examSections", "list", testId] });
      addToast("Bo'lim yangilandi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yangilab bo'lmadi"),
  });
}

// --- ExamModule ---

export function useExamModulesForTest(testId: string | undefined) {
  const query = useQuery({
    queryKey: ["examModules", "list", "byTest", testId],
    queryFn: () => examModulesApi.listForTest(testId as string),
    enabled: !!testId,
  });
  useToastOnQueryError(query);
  return query;
}

export function useCreateExamModule(testId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: ExamModuleCreateRequest) => examModulesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["examModules", "list", "byTest", testId] });
      addToast("Modul yaratildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yaratib bo'lmadi"),
  });
}

export function useUpdateExamModule(testId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: ({ moduleId, data }: { moduleId: string; data: ExamModuleUpdateRequest }) =>
      examModulesApi.update(moduleId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["examModules", "list", "byTest", testId] });
      addToast("Modul yangilandi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yangilab bo'lmadi"),
  });
}

// --- QuestionGroup ---

export function useQuestionGroupsList(testId: string | undefined) {
  const query = useQuery({
    queryKey: ["questionGroups", "list", testId],
    queryFn: () => questionGroupsApi.list(testId as string),
    enabled: !!testId,
  });
  useToastOnQueryError(query);
  return query;
}

export function useCreateQuestionGroup(testId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: QuestionGroupCreateRequest) => questionGroupsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["questionGroups", "list", testId] });
      addToast("Guruh yaratildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yaratib bo'lmadi"),
  });
}

export function useUpdateQuestionGroup(testId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: ({ groupId, data }: { groupId: string; data: QuestionGroupUpdateRequest }) =>
      questionGroupsApi.update(groupId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["questionGroups", "list", testId] });
      addToast("Guruh yangilandi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yangilab bo'lmadi"),
  });
}

export function useDeleteQuestionGroup(testId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (groupId: string) => questionGroupsApi.remove(groupId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["questionGroups", "list", testId] });
      addToast("Guruh o'chirildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "O'chirib bo'lmadi"),
  });
}

// --- RoutingThresholdRule (Sprint 75 completion) ---

export function useRoutingThresholdRulesList(testId: string | undefined) {
  const query = useQuery({
    queryKey: ["routingThresholdRules", "list", testId],
    queryFn: () => routingThresholdRulesApi.list(testId as string),
    enabled: !!testId,
  });
  useToastOnQueryError(query);
  return query;
}

export function useCreateRoutingThresholdRule(testId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: RoutingThresholdRuleCreateRequest) => routingThresholdRulesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["routingThresholdRules", "list", testId] });
      addToast("Yo'naltirish qoidasi yaratildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yaratib bo'lmadi"),
  });
}

export function useUpdateRoutingThresholdRule(testId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: ({ ruleId, data }: { ruleId: string; data: RoutingThresholdRuleUpdateRequest }) =>
      routingThresholdRulesApi.update(ruleId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["routingThresholdRules", "list", testId] });
      addToast("Yo'naltirish qoidasi yangilandi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yangilab bo'lmadi"),
  });
}

export function useDeleteRoutingThresholdRule(testId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (ruleId: string) => routingThresholdRulesApi.remove(ruleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["routingThresholdRules", "list", testId] });
      addToast("Yo'naltirish qoidasi o'chirildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "O'chirib bo'lmadi"),
  });
}
