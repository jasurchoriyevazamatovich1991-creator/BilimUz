/**
 * Grades data hooks — same shape as hooks/useSubjects.ts. Note:
 * `useUpdateGrade` only ever accepts `{status}` (matches
 * GradeUpdateRequest exactly — no name field, see api/grades.ts).
 */
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { gradesApi, type GradeCreateRequest, type GradeListParams, type GradeUpdateRequest } from "@/api/grades";
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

export function useGradesList(params: GradeListParams) {
  const query = useQuery({ queryKey: ["grades", "list", params], queryFn: () => gradesApi.list(params) });
  useToastOnQueryError(query);
  return query;
}

export function useGrade(gradeId: string | undefined) {
  const query = useQuery({
    queryKey: ["grades", "detail", gradeId],
    queryFn: () => gradesApi.get(gradeId as string),
    enabled: !!gradeId,
  });
  useToastOnQueryError(query);
  return query;
}

export function useCreateGrade() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: GradeCreateRequest) => gradesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["grades", "list"] });
      addToast("Sinf yaratildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yaratib bo'lmadi"),
  });
}

export function useUpdateGrade(gradeId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: GradeUpdateRequest) => gradesApi.update(gradeId, data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["grades", "list"] });
      queryClient.setQueryData(["grades", "detail", gradeId], updated);
      addToast("Sinf yangilandi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yangilab bo'lmadi"),
  });
}

export function useDeleteGrade() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (gradeId: string) => gradesApi.remove(gradeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["grades", "list"] });
      addToast("Sinf o'chirildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "O'chirib bo'lmadi"),
  });
}
