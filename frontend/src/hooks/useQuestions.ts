/**
 * Question data hooks, plus the batched Options/Media "Save" mutation
 * (approved decision 6): the form accumulates all option/media edits
 * in LOCAL state (see QuestionFormPage.tsx), and only on "Saqlash" does
 * this hook execute the diff — one real API call per actual change
 * (add/update/delete), never per keystroke.
 *
 * Cache strategy (approved decision 8): Option/Media mutations
 * invalidate ONLY Questions' own cache (`["questions", ...]`) — never
 * `["tests", ...]`, verified directly (grep-checked, no cross-reference
 * exists in this file).
 */
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import {
  questionsApi,
  type MediaCreateRequest,
  type OptionCreateRequest,
  type OptionUpdateRequest,
  type QuestionCreateRequest,
  type QuestionListParams,
  type QuestionUpdateRequest,
} from "@/api/questions";
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

export function useQuestionsList(params: QuestionListParams) {
  const query = useQuery({ queryKey: ["questions", "list", params], queryFn: () => questionsApi.list(params) });
  useToastOnQueryError(query);
  return query;
}

export function useQuestion(questionId: string | undefined) {
  const query = useQuery({
    queryKey: ["questions", "detail", questionId],
    queryFn: () => questionsApi.get(questionId as string),
    enabled: !!questionId,
  });
  useToastOnQueryError(query);
  return query;
}

export function useCreateQuestion() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: QuestionCreateRequest) => questionsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["questions", "list"] });
      addToast("Savol yaratildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yaratib bo'lmadi"),
  });
}

export function useUpdateQuestion(questionId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: QuestionUpdateRequest) => questionsApi.update(questionId, data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["questions", "list"] });
      queryClient.setQueryData(["questions", "detail", questionId], updated);
      addToast("Savol yangilandi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yangilab bo'lmadi"),
  });
}

export function useDeleteQuestion() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (questionId: string) => questionsApi.remove(questionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["questions", "list"] });
      addToast("Savol o'chirildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "O'chirib bo'lmadi"),
  });
}

export interface OptionsDiff {
  toAdd: OptionCreateRequest[];
  toUpdate: Array<{ id: string; data: OptionUpdateRequest }>;
  toDelete: string[];
}

export interface MediaDiff {
  toAdd: MediaCreateRequest[];
  toDelete: string[];
}

/**
 * Executes a computed diff against the real granular endpoints — one
 * call per real change, sequential (not parallel, to keep error
 * handling simple and predictable if one call in the batch fails).
 * Invalidates ONLY the parent Question's caches on success — approved
 * decision 8, never touches ["tests", ...].
 */
export function useSaveQuestionOptionsAndMedia(questionId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: async ({ optionsDiff, mediaDiff }: { optionsDiff: OptionsDiff; mediaDiff: MediaDiff }) => {
      for (const option of optionsDiff.toAdd) {
        await questionsApi.addOption(questionId, option);
      }
      for (const { id, data } of optionsDiff.toUpdate) {
        await questionsApi.updateOption(questionId, id, data);
      }
      for (const id of optionsDiff.toDelete) {
        await questionsApi.deleteOption(questionId, id);
      }
      for (const media of mediaDiff.toAdd) {
        await questionsApi.addMedia(questionId, media);
      }
      for (const id of mediaDiff.toDelete) {
        await questionsApi.deleteMedia(questionId, id);
      }
      return questionsApi.get(questionId); // fetch the final, authoritative state once all changes are applied
    },
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["questions", "list"] });
      queryClient.setQueryData(["questions", "detail", questionId], updated);
      addToast("Variantlar va media saqlandi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Saqlab bo'lmadi"),
  });
}
