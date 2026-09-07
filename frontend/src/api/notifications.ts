/**
 * New file — every shape verified directly against real backend
 * app/modules/notifications/{schemas,router}.py before writing.
 * Paths confirmed: GET /notifications/me, PATCH /notifications/{id}/read,
 * PATCH /notifications/me/read-all. No fields invented — NotificationOut
 * has exactly: id, user_id, title, message, channel, is_read, created_at.
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface NotificationOut {
  id: string;
  user_id: string;
  title: string;
  message: string;
  channel: string;
  is_read: boolean;
  created_at: string;
}

export interface NotificationListParams {
  page: number;
  per_page: number;
  is_read?: boolean;
}

export const notificationsApi = {
  listMine: (params: NotificationListParams) =>
    unwrap<PaginatedResponse<NotificationOut>>(httpClient.get("/notifications/me", { params })),

  /** Reliable unread count via pagination metadata (per_page=1) — not a
   * client-side count over an unbounded list, since the list endpoint
   * is paginated and a full-list count would be wrong past page 1. */
  unreadCount: async (): Promise<number> => {
    const result = await unwrap<PaginatedResponse<NotificationOut>>(
      httpClient.get("/notifications/me", { params: { per_page: 1, is_read: false } }),
    );
    return result.meta.total;
  },

  markRead: (notificationId: string) => unwrap<NotificationOut>(httpClient.patch(`/notifications/${notificationId}/read`)),

  markAllRead: () => unwrap<{ marked_count: number }>(httpClient.patch("/notifications/me/read-all")),
};
