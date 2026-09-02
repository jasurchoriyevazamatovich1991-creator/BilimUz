/**
 * Tests data hooks — same shape as hooks/useTopics.ts (Sprint 17).
 * `usePublishTest` is a new action-mutation shape (a state transition,
 * not a field edit) — invalidates the same list/detail keys as any
 * other successful mutation, nothing new needed there.
 */
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { testsApi, type TestCreateRequest, type TestListParams, type TestUpdateRequest } from "@/api/tests";
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

export function useTestsList(params: TestListParams) {
  const query = useQuery({ queryKey: ["tests", "list", params], queryFn: () => testsApi.list(params) });
  useToastOnQueryError(query);
  return query;
}

export function useTest(testId: string | undefined) {
  const query = useQuery({
    queryKey: ["tests", "detail", testId],
    queryFn: () => testsApi.get(testId as string),
    enabled: !!testId,
  });
  useToastOnQueryError(query);
  return query;
}

export function useCreateTest() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: TestCreateRequest) => testsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tests", "list"] });
      addToast("Test yaratildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yaratib bo'lmadi"),
  });
}

export function useUpdateTest(testId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: TestUpdateRequest) => testsApi.update(testId, data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["tests", "list"] });
      queryClient.setQueryData(["tests", "detail", testId], updated);
      addToast("Test yangilandi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yangilab bo'lmadi"),
  });
}

export function usePublishTest(testId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: () => testsApi.publish(testId),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["tests", "list"] });
      queryClient.setQueryData(["tests", "detail", testId], updated);
      addToast("Test e'lon qilindi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "E'lon qilib bo'lmadi"),
  });
}

export function useDeleteTest() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (testId: string) => testsApi.remove(testId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tests", "list"] });
      addToast("Test o'chirildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "O'chirib bo'lmadi"),
  });
}
