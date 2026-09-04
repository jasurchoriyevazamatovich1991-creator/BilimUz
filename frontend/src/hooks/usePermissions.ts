/**
 * New file — Permission CRUD + Role<->Permission grant management.
 * Same shape as hooks/useRoles.ts's Sprint 22 additions.
 */
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import {
  permissionsApi,
  type PermissionCreateRequest,
  type PermissionListParams,
  type PermissionUpdateRequest,
} from "@/api/permissions";
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

export function usePermissionsList(params: PermissionListParams) {
  const query = useQuery({ queryKey: ["permissions", "list", params], queryFn: () => permissionsApi.list(params) });
  useToastOnQueryError(query);
  return query;
}

export function usePermission(permissionId: string | undefined) {
  const query = useQuery({
    queryKey: ["permissions", "detail", permissionId],
    queryFn: () => permissionsApi.get(permissionId as string),
    enabled: !!permissionId,
  });
  useToastOnQueryError(query);
  return query;
}

export function useCreatePermission() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: PermissionCreateRequest) => permissionsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["permissions"] });
      addToast("Ruxsat yaratildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yaratib bo'lmadi"),
  });
}

export function useUpdatePermission(permissionId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: PermissionUpdateRequest) => permissionsApi.update(permissionId, data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["permissions"] });
      queryClient.setQueryData(["permissions", "detail", permissionId], updated);
      addToast("Ruxsat yangilandi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Yangilab bo'lmadi"),
  });
}

export function useDeletePermission() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (permissionId: string) => permissionsApi.remove(permissionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["permissions"] });
      addToast("Ruxsat o'chirildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "O'chirib bo'lmadi"),
  });
}

// --- Role <-> Permission grants ---

export function useRolePermissions(roleId: string | undefined) {
  const query = useQuery({
    queryKey: ["permissions", "for-role", roleId],
    queryFn: () => permissionsApi.listForRole(roleId as string),
    enabled: !!roleId,
  });
  useToastOnQueryError(query);
  return query;
}

export function useAssignPermission(roleId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (permissionId: string) => permissionsApi.assignToRole(roleId, permissionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["permissions", "for-role", roleId] });
      addToast("Ruxsat biriktirildi", "success");
    },
    // A 409 here (RolePermissionAlreadyExistsException) is a real,
    // expected outcome if a race lets someone assign the same
    // permission twice — surfaced via the normal toast like any other
    // error, no invented special-case handling.
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Biriktirib bo'lmadi"),
  });
}

export function useRevokePermission(roleId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (permissionId: string) => permissionsApi.revokeFromRole(roleId, permissionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["permissions", "for-role", roleId] });
      addToast("Ruxsat olib tashlandi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Olib tashlab bo'lmadi"),
  });
}
