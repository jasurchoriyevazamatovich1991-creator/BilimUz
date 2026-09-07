/**
 * Notification hooks — same shape as every prior data hook in the
 * project (toast-via-useEffect on query error, mutation invalidation
 * on success). `useUnreadCount` uses a short staleTime so the Header
 * bell doesn't hammer the API on every render, but still reflects
 * changes shortly after mark-read/mark-all-read (both invalidate it).
 */
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { notificationsApi, type NotificationListParams } from "@/api/notifications";
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

export function useMyNotifications(params: NotificationListParams) {
  const query = useQuery({ queryKey: ["notifications", "list", params], queryFn: () => notificationsApi.listMine(params) });
  useToastOnQueryError(query);
  return query;
}

export function useUnreadNotificationCount(enabled = true) {
  return useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: notificationsApi.unreadCount,
    staleTime: 30 * 1000, // 30s — the Header bell shouldn't refetch on every render, but stays reasonably fresh
    enabled,
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (notificationId: string) => notificationsApi.markRead(notificationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications", "list"] });
      queryClient.invalidateQueries({ queryKey: ["notifications", "unread-count"] });
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "O'qilgan deb belgilab bo'lmadi"),
  });
}

export function useMarkAllNotificationsRead() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications", "list"] });
      queryClient.invalidateQueries({ queryKey: ["notifications", "unread-count"] });
      addToast("Barchasi o'qilgan deb belgilandi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Bajarib bo'lmadi"),
  });
}
