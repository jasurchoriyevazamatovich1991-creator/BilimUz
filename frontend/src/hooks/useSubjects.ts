/**
 * Subjects data hooks — same shape as hooks/useSchools.ts (Sprint 16):
 * list/get + create/update/delete mutations, toast-via-useEffect,
 * broad list-key invalidation on mutation success.
 */
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { subjectsApi, type SubjectCreateRequest, type SubjectListParams, type SubjectUpdateRequest } from "@/api/subjects";
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

export function useSubjectsList(params: SubjectListParams) {
  const query = useQuery({ queryKey: ["subjects", "list", params], queryFn: () => subjectsApi.list(params) });
  useToastOnQueryError(query);
  return query;
}

export function useSubject(subjectId: string | undefined) {
  const query = useQuery({
    queryKey: ["subjects", "detail", subjectId],
    queryFn: () => subjectsApi.get(subjectId as string),
    enabled: !!subjectId,
  });
  useToastOnQueryError(query);
  return query;
}

export function useCreateSubject() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: SubjectCreateRequest) => subjectsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subjects", "list"] });
      addToast("Fan yaratildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yaratib bo'lmadi"),
  });
}

export function useUpdateSubject(subjectId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: SubjectUpdateRequest) => subjectsApi.update(subjectId, data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["subjects", "list"] });
      queryClient.setQueryData(["subjects", "detail", subjectId], updated);
      addToast("Fan yangilandi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yangilab bo'lmadi"),
  });
}

export function useDeleteSubject() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (subjectId: string) => subjectsApi.remove(subjectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subjects", "list"] });
      addToast("Fan o'chirildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "O'chirib bo'lmadi"),
  });
}
