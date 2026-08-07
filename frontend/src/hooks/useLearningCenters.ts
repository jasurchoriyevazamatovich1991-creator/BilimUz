/**
 * Learning Centers data hooks — same shape as hooks/useSchools.ts,
 * deliberately not shared/abstracted (approved decision: two separate
 * pages/hooks, not one generic mega-component).
 */
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import {
  learningCentersApi,
  type LearningCenterCreateRequest,
  type LearningCenterListParams,
  type LearningCenterUpdateRequest,
} from "@/api/learningCenters";
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

export function useLearningCentersList(params: LearningCenterListParams) {
  const query = useQuery({ queryKey: ["learningCenters", "list", params], queryFn: () => learningCentersApi.list(params) });
  useToastOnQueryError(query);
  return query;
}

export function useLearningCenter(centerId: string | undefined) {
  const query = useQuery({
    queryKey: ["learningCenters", "detail", centerId],
    queryFn: () => learningCentersApi.get(centerId as string),
    enabled: !!centerId,
  });
  useToastOnQueryError(query);
  return query;
}

export function useCreateLearningCenter() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: LearningCenterCreateRequest) => learningCentersApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["learningCenters", "list"] });
      addToast("O'quv markazi yaratildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yaratib bo'lmadi"),
  });
}

export function useUpdateLearningCenter(centerId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: LearningCenterUpdateRequest) => learningCentersApi.update(centerId, data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["learningCenters", "list"] });
      queryClient.setQueryData(["learningCenters", "detail", centerId], updated);
      addToast("O'quv markazi yangilandi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yangilab bo'lmadi"),
  });
}

export function useDeleteLearningCenter() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (centerId: string) => learningCentersApi.remove(centerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["learningCenters", "list"] });
      addToast("O'quv markazi o'chirildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "O'chirib bo'lmadi"),
  });
}
