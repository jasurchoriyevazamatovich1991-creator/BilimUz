/**
 * New hook (approved decision — NOT an extension of utils/roleConfig.ts,
 * which maps role NAME -> panel and is unrelated to this id -> role
 * lookup). Wraps GET /roles via TanStack Query, cached — roles change
 * rarely, a long staleTime avoids refetching on every Users page visit.
 *
 * Sprint 22 extension: full Roles CRUD hooks added below
 * (useRolesList/useRole/useCreateRole/useUpdateRole/useDeleteRole) —
 * useRoles()/useRoleNameLookup() above are completely unchanged.
 */
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { rolesApi, type RoleCreateRequest, type RoleListParams, type RoleUpdateRequest } from "@/api/roles";
import { useToastStore } from "@/store/toastStore";
import { ApiError } from "@/api/client";

export function useRoles() {
  return useQuery({
    queryKey: ["roles", "list"],
    queryFn: rolesApi.list,
    staleTime: 10 * 60 * 1000, // 10 minutes — roles are near-static reference data
  });
}

/** Convenience: role_id -> role name, for table cells. Returns the raw
 * id as a fallback while roles are still loading/unavailable, so the
 * table never shows a blank cell. */
export function useRoleNameLookup(): (roleId: string) => string {
  const { data: roles } = useRoles();
  return (roleId: string) => roles?.find((r) => r.id === roleId)?.name ?? roleId;
}

// --- Sprint 22 additions: full Roles CRUD ---

function useToastOnQueryError(query: UseQueryResult<unknown, unknown>) {
  const addToast = useToastStore((s) => s.addToast);
  useEffect(() => {
    if (query.isError) {
      addToast(query.error instanceof ApiError ? query.error.message : "Ma'lumot yuklanmadi");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.isError, query.error]);
}

export function useRolesList(params: RoleListParams) {
  const query = useQuery({ queryKey: ["roles", "list-paginated", params], queryFn: () => rolesApi.listPaginated(params) });
  useToastOnQueryError(query);
  return query;
}

export function useRole(roleId: string | undefined) {
  const query = useQuery({
    queryKey: ["roles", "detail", roleId],
    queryFn: () => rolesApi.get(roleId as string),
    enabled: !!roleId,
  });
  useToastOnQueryError(query);
  return query;
}

export function useCreateRole() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: RoleCreateRequest) => rolesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roles"] });
      addToast("Rol yaratildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yaratib bo'lmadi"),
  });
}

export function useUpdateRole(roleId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: RoleUpdateRequest) => rolesApi.update(roleId, data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["roles"] });
      queryClient.setQueryData(["roles", "detail", roleId], updated);
      addToast("Rol yangilandi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yangilab bo'lmadi"),
  });
}

export function useDeleteRole() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (roleId: string) => rolesApi.remove(roleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roles"] });
      addToast("Rol o'chirildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "O'chirib bo'lmadi"),
  });
}
