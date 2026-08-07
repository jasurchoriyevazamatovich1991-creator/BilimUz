/**
 * Topics data hooks — same shape as hooks/useGrades.ts. Cache
 * invalidation is scoped to Topics' own mutations ONLY (approved
 * decision 5) — Subjects/Grades mutations never invalidate
 * ["topics", ...] here, and Subjects/Grades' own hooks (useSubjects.ts,
 * useGrades.ts) never reference the "topics" query key either. The
 * existing React Query strategy (per-module list-key invalidation) is
 * unchanged, not extended with cross-module invalidation.
 */
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { topicsApi, type TopicCreateRequest, type TopicListParams, type TopicUpdateRequest } from "@/api/topics";
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

export function useTopicsList(params: TopicListParams) {
  const query = useQuery({ queryKey: ["topics", "list", params], queryFn: () => topicsApi.list(params) });
  useToastOnQueryError(query);
  return query;
}

export function useTopic(topicId: string | undefined) {
  const query = useQuery({
    queryKey: ["topics", "detail", topicId],
    queryFn: () => topicsApi.get(topicId as string),
    enabled: !!topicId,
  });
  useToastOnQueryError(query);
  return query;
}

export function useCreateTopic() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: TopicCreateRequest) => topicsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["topics", "list"] });
      addToast("Mavzu yaratildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yaratib bo'lmadi"),
  });
}

export function useUpdateTopic(topicId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: TopicUpdateRequest) => topicsApi.update(topicId, data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["topics", "list"] });
      queryClient.setQueryData(["topics", "detail", topicId], updated);
      addToast("Mavzu yangilandi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yangilab bo'lmadi"),
  });
}

export function useDeleteTopic() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (topicId: string) => topicsApi.remove(topicId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["topics", "list"] });
      addToast("Mavzu o'chirildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "O'chirib bo'lmadi"),
  });
}
