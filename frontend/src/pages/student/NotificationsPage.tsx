/**
 * Student-facing (though the real backend endpoint works for any
 * authenticated user — this page is mounted only under the Student
 * panel this sprint, per approved scope). Shows ONLY real
 * NotificationOut fields: title, message, channel, is_read, created_at.
 * No per-notification "type" icon or invented category — `channel`
 * exists but isn't a user-facing categorization field.
 */
import { useState } from "react";
import { ErrorState } from "@/components/layout/ErrorState";
import { Button } from "@/components/ui/button";
import { useMyNotifications, useMarkNotificationRead, useMarkAllNotificationsRead, useUnreadNotificationCount } from "@/hooks/useNotifications";

const PER_PAGE = 20;

export function NotificationsPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading, isError } = useMyNotifications({ page, per_page: PER_PAGE });
  const { data: unreadCount } = useUnreadNotificationCount();
  const markRead = useMarkNotificationRead();
  const markAllRead = useMarkAllNotificationsRead();

  if (isError) return <ErrorState title="Bildirishnomalar" />;

  const hasUnread = (unreadCount ?? 0) > 0;

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">Bildirishnomalar</h1>
        {hasUnread ? (
          <Button variant="outline" onClick={() => markAllRead.mutate()} disabled={markAllRead.isPending}>
            {markAllRead.isPending ? "..." : "Barchasini o'qilgan deb belgilash"}
          </Button>
        ) : null}
      </div>

      {isLoading ? (
        <p className="text-sm text-foreground/50">Yuklanmoqda...</p>
      ) : data && data.items.length > 0 ? (
        <ul className="space-y-2">
          {data.items.map((notification) => (
            <li
              key={notification.id}
              onClick={() => {
                if (!notification.is_read) markRead.mutate(notification.id);
              }}
              className={`rounded-lg border p-4 ${
                notification.is_read
                  ? "border-border bg-background"
                  : "cursor-pointer border-primary/30 bg-primary/5 hover:bg-primary/10"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    {!notification.is_read ? <span className="h-2 w-2 shrink-0 rounded-full bg-primary" aria-label="O'qilmagan" /> : null}
                    <h3 className="truncate font-medium text-foreground">{notification.title}</h3>
                  </div>
                  <p className="mt-1 text-sm text-foreground/70">{notification.message}</p>
                  <p className="mt-2 text-xs text-foreground/40">{new Date(notification.created_at).toLocaleString()}</p>
                </div>
                {!notification.is_read ? (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      markRead.mutate(notification.id);
                    }}
                    className="shrink-0 text-sm text-primary hover:underline"
                  >
                    O'qildi
                  </button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="rounded-lg border border-dashed border-border p-12 text-center">
          <p className="text-sm text-foreground/60">Hozircha bildirishnomalar yo'q.</p>
        </div>
      )}

      {data && data.meta.total_pages > 1 ? (
        <div className="mt-4 flex items-center justify-between text-sm text-foreground/60">
          <span>{data.meta.total} tadan {(page - 1) * PER_PAGE + 1}-{Math.min(page * PER_PAGE, data.meta.total)}</span>
          <div className="flex gap-2">
            <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="rounded-md border border-border px-3 py-1.5 disabled:opacity-40">Oldingi</button>
            <button type="button" disabled={page >= data.meta.total_pages} onClick={() => setPage((p) => p + 1)} className="rounded-md border border-border px-3 py-1.5 disabled:opacity-40">Keyingi</button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
