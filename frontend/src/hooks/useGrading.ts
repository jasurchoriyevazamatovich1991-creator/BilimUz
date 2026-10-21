/** Task 5 — TanStack Query hooks for manual grading. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { gradingApi, type DraftSaveRequest, type ManualComponent, type QueueStatus, type RubricCreateRequest } from "@/api/grading";
import { ApiError } from "@/api/client";
import { useToastStore } from "@/store/toastStore";

export function useRubrics(component?: ManualComponent) {
  return useQuery({ queryKey: ["grading", "rubrics", component ?? "all"], queryFn: () => gradingApi.listRubrics(component), retry: false });
}

export function useCreateRubric() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);
  return useMutation({
    mutationFn: (data: RubricCreateRequest) => gradingApi.createRubric(data),
    onSuccess: (r) => {
      queryClient.invalidateQueries({ queryKey: ["grading", "rubrics"] });
      addToast(`Rubrika ${r.version}-versiya sifatida e'lon qilindi`, "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Rubrika saqlanmadi"),
  });
}

export function useGradingQueue(status: QueueStatus | undefined, page: number) {
  return useQuery({
    queryKey: ["grading", "queue", status ?? "all", page],
    queryFn: () => gradingApi.listQueue({ ...(status ? { status } : {}), page, per_page: 20 }),
    retry: false,
  });
}

export function useSubmission(attemptId: string | undefined, questionId: string | undefined) {
  return useQuery({
    queryKey: ["grading", "submission", attemptId, questionId],
    queryFn: () => gradingApi.getSubmission(attemptId as string, questionId as string),
    enabled: !!attemptId && !!questionId,
    retry: false,
  });
}

function useItemMutation<TVars>(attemptId: string, questionId: string, fn: (vars: TVars) => Promise<unknown>, success: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["grading", "submission", attemptId, questionId] });
      queryClient.invalidateQueries({ queryKey: ["grading", "queue"] });
      addToast(success, "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Amal bajarilmadi"),
  });
}

export function useSaveDraft(attemptId: string, questionId: string) {
  return useItemMutation(attemptId, questionId, (data: DraftSaveRequest) => gradingApi.saveDraft(attemptId, questionId, data), "Qoralama saqlandi");
}

export function useFinalizeReview(attemptId: string, questionId: string) {
  return useItemMutation(attemptId, questionId, () => gradingApi.finalize(attemptId, questionId), "Baho yakunlandi");
}

export function useReviseReview(attemptId: string, questionId: string) {
  return useItemMutation(attemptId, questionId, (reason: string) => gradingApi.revise(attemptId, questionId, reason), "Tuzatish qoralamasi ochildi");
}
