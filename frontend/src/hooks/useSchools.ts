/**
 * Schools data hooks — same shape as hooks/useUsers.ts (Sprint 15):
 * list/get + create/update/delete mutations, toast-via-useEffect on
 * query error, broad list-key invalidation on mutation success.
 */
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { schoolsApi, type SchoolCreateRequest, type SchoolListParams, type SchoolUpdateRequest } from "@/api/schools";
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

export function useSchoolsList(params: SchoolListParams) {
  const query = useQuery({ queryKey: ["schools", "list", params], queryFn: () => schoolsApi.list(params) });
  useToastOnQueryError(query);
  return query;
}

export function useSchool(schoolId: string | undefined) {
  const query = useQuery({
    queryKey: ["schools", "detail", schoolId],
    queryFn: () => schoolsApi.get(schoolId as string),
    enabled: !!schoolId,
  });
  useToastOnQueryError(query);
  return query;
}

export function useCreateSchool() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: SchoolCreateRequest) => schoolsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schools", "list"] });
      addToast("Maktab yaratildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yaratib bo'lmadi"),
  });
}

export function useUpdateSchool(schoolId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: SchoolUpdateRequest) => schoolsApi.update(schoolId, data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["schools", "list"] });
      queryClient.setQueryData(["schools", "detail", schoolId], updated);
      addToast("Maktab yangilandi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yangilab bo'lmadi"),
  });
}

export function useDeleteSchool() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (schoolId: string) => schoolsApi.remove(schoolId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schools", "list"] });
      addToast("Maktab o'chirildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "O'chirib bo'lmadi"),
  });
}
