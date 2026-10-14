/**
 * AI Center hooks — same shape as useNotifications.ts (toast-on-error +
 * TanStack Query). Sprint 88 scope: one ongoing conversation per
 * student, matching the backend's real contract and NOT inventing any
 * new persistent storage — the actual message history is the backend's
 * existing AiChat/AiHistoryEntry data, fetched fresh every time; nothing
 * extra is cached in localStorage/sessionStorage.
 *
 * `useActiveAiChatId()` reuses the user's most recent chat (GET
 * /ai/chats/me, sorted created_at desc per repository.py) if one
 * exists, and only calls POST /ai/chats to start a new one when the
 * user genuinely has none yet — it does not create a new chat on every
 * page visit.
 */
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { aiApi } from "@/api/ai";
import { useToastStore } from "@/store/toastStore";
import { ApiError } from "@/api/client";

function useToastOnQueryError(query: UseQueryResult<unknown, unknown>, fallback: string) {
  const addToast = useToastStore((s) => s.addToast);
  useEffect(() => {
    if (query.isError) {
      addToast(query.error instanceof ApiError ? query.error.message : fallback);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.isError, query.error]);
}

/** Resolves the chat id to use: the most recent existing chat, or a
 * freshly created one if the user has none yet. */
export function useActiveAiChatId() {
  const queryClient = useQueryClient();

  const myChatsQuery = useQuery({
    queryKey: ["ai", "chats", "mine", "latest"],
    queryFn: () => aiApi.myChats(1, 1),
  });

  const startChat = useMutation({
    mutationFn: () => aiApi.startChat(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai", "chats", "mine", "latest"] });
    },
  });

  const existingChatId = myChatsQuery.data?.items[0]?.id ?? null;

  useEffect(() => {
    // Only create a chat once we know for certain there isn't one
    // already (query settled, zero items) — never while still loading,
    // and never more than once per missing-chat state.
    if (myChatsQuery.isSuccess && !existingChatId && !startChat.isPending && !startChat.isSuccess) {
      startChat.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [myChatsQuery.isSuccess, existingChatId]);

  const chatId = existingChatId ?? startChat.data?.id ?? null;
  // Still resolving as long as we have neither a chat id nor a terminal
  // failure — covers "list still loading" and "list done, create still
  // in flight" in one condition.
  const isResolving = chatId === null && !startChat.isError && !myChatsQuery.isError;
  const isError = myChatsQuery.isError || startChat.isError;

  return { chatId, isResolving, isError };
}

/** The active chat's full message history. */
export function useAiChatHistory(chatId: string | null) {
  const query = useQuery({
    queryKey: ["ai", "chats", chatId, "detail"],
    queryFn: () => aiApi.getChat(chatId as string),
    enabled: Boolean(chatId),
  });
  useToastOnQueryError(query, "Suhbat tarixini yuklab bo'lmadi");
  return query;
}

/** Sends one message into the active chat. Deliberately NO automatic
 * retry — TanStack Query mutations never auto-retry unless `retry` is
 * explicitly set (unlike queries, where App.tsx sets `retry: 1`; this
 * mutation does not opt in), so a failed send surfaces its real error
 * once and the page offers a manual "Qayta urinish" button instead of
 * silently resending (which could duplicate a request the backend
 * already rate-limits). `isPending` also gates the page's send button
 * so a user can't double-submit the same message while one is already
 * in flight. */
export function useSendAiMessage(chatId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (content: string) => aiApi.sendMessage(chatId as string, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai", "chats", chatId, "detail"] });
    },
  });
}
