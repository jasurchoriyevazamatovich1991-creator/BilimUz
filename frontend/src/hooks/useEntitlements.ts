/**
 * Mock Test Entitlements data hooks (Admin Management of Mock Test
 * Entitlements, Task D). Same shape as hooks/useUsers.ts: query +
 * toast-via-useEffect on error, broad list-key invalidation on mutation
 * success (simpler and correct-by-construction, same reasoning as that
 * file's own docstring).
 */
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import {
  entitlementsApi,
  type EntitlementExtendRequest,
  type EntitlementGrantRequest,
  type EntitlementRevokeRequest,
} from "@/api/entitlements";
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

export function useUserEntitlements(userId: string | undefined) {
  const query = useQuery({
    queryKey: ["entitlements", "admin", "user", userId],
    queryFn: () => entitlementsApi.listForUser(userId as string),
    enabled: !!userId,
  });
  useToastOnQueryError(query);
  return query;
}

export function useMyEntitlements() {
  const query = useQuery({ queryKey: ["entitlements", "me"], queryFn: () => entitlementsApi.listMine() });
  useToastOnQueryError(query);
  return query;
}

export function useGrantEntitlement(userId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: EntitlementGrantRequest) => entitlementsApi.grant(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entitlements", "admin", "user", userId] });
      addToast("Mock Test ruxsati berildi", "success");
    },
    onError: (error) => {
      addToast(error instanceof ApiError ? error.message : "Ruxsat berib bo'lmadi");
    },
  });
}

export function useExtendEntitlement(userId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: ({ entitlementId, data }: { entitlementId: string; data: EntitlementExtendRequest }) =>
      entitlementsApi.extend(entitlementId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entitlements", "admin", "user", userId] });
      addToast("Ruxsat muddati yangilandi", "success");
    },
    onError: (error) => {
      addToast(error instanceof ApiError ? error.message : "Muddatni yangilab bo'lmadi");
    },
  });
}

export function useRevokeEntitlement(userId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: ({ entitlementId, data }: { entitlementId: string; data?: EntitlementRevokeRequest }) =>
      entitlementsApi.revoke(entitlementId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entitlements", "admin", "user", userId] });
      addToast("Ruxsat bekor qilindi", "success");
    },
    onError: (error) => {
      addToast(error instanceof ApiError ? error.message : "Bekor qilib bo'lmadi");
    },
  });
}
