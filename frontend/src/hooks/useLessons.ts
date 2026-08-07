/**
 * Lessons data hooks — same shape as hooks/useTopics.ts (Sprint 17).
 * Cache invalidation scoped to Lessons' own mutations only — reading
 * Topics for the picker/lookup never invalidates or is invalidated by
 * Lessons' cache (same isolation discipline as Topics' own relationship
 * to Subjects/Grades, approved decision 5 of Sprint 17, carried forward
 * unchanged here).
 */
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { lessonsApi, type LessonCreateRequest, type LessonListParams, type LessonUpdateRequest } from "@/api/lessons";
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

export function useLessonsList(params: LessonListParams) {
  const query = useQuery({ queryKey: ["lessons", "list", params], queryFn: () => lessonsApi.list(params) });
  useToastOnQueryError(query);
  return query;
}

export function useLesson(lessonId: string | undefined) {
  const query = useQuery({
    queryKey: ["lessons", "detail", lessonId],
    queryFn: () => lessonsApi.get(lessonId as string),
    enabled: !!lessonId,
  });
  useToastOnQueryError(query);
  return query;
}

export function useCreateLesson() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: LessonCreateRequest) => lessonsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["lessons", "list"] });
      addToast("Dars yaratildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yaratib bo'lmadi"),
  });
}

export function useUpdateLesson(lessonId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: LessonUpdateRequest) => lessonsApi.update(lessonId, data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["lessons", "list"] });
      queryClient.setQueryData(["lessons", "detail", lessonId], updated);
      addToast("Dars yangilandi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yangilab bo'lmadi"),
  });
}

export function useDeleteLesson() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (lessonId: string) => lessonsApi.remove(lessonId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["lessons", "list"] });
      addToast("Dars o'chirildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "O'chirib bo'lmadi"),
  });
}
