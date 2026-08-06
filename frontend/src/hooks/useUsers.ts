/**
 * Users data hooks — list (paginated/filtered), get one, update,
 * change role. Same error-toast pattern as useDashboardStats.ts
 * (useEffect, not render-body — see that file's docstring for why).
 * Cache strategy: on successful update/role-change, invalidate
 * ["users", "list"] broadly (all pages/filters) rather than manually
 * patching cache entries — simpler, correct-by-construction.
 */
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { usersApi, type UserAdminUpdateRequest, type UserListParams } from "@/api/users";
import { useToastStore } from "@/store/toastStore";
import { ApiError } from "@/api/client";

function useToastOnQueryError(query: UseQueryResult<unknown, unknown>) {
  const addToast = useToastStore((s) => s.addToast);

  useEffect(() => {
    if (query.isError) {
      const message = query.error instanceof ApiError ? query.error.message : "Ma'lumot yuklanmadi";
      addToast(message);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.isError, query.error]);
}

export function useUsersList(params: UserListParams) {
  const query = useQuery({
    queryKey: ["users", "list", params],
    queryFn: () => usersApi.list(params),
  });
  useToastOnQueryError(query);
  return query;
}

export function useUser(userId: string | undefined) {
  const query = useQuery({
    queryKey: ["users", "detail", userId],
    queryFn: () => usersApi.get(userId as string),
    enabled: !!userId,
  });
  useToastOnQueryError(query);
  return query;
}

export function useUpdateUser(userId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: UserAdminUpdateRequest) => usersApi.update(userId, data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["users", "list"] });
      queryClient.setQueryData(["users", "detail", userId], updated);
      addToast("Foydalanuvchi yangilandi", "success");
    },
    onError: (error) => {
      addToast(error instanceof ApiError ? error.message : "Yangilab bo'lmadi");
    },
  });
}

export function useChangeUserRole(userId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (roleId: string) => usersApi.changeRole(userId, roleId),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["users", "list"] });
      queryClient.setQueryData(["users", "detail", userId], updated);
      addToast("Rol o'zgartirildi", "success");
    },
    onError: (error) => {
      addToast(error instanceof ApiError ? error.message : "Rolni o'zgartirib bo'lmadi");
    },
  });
}
