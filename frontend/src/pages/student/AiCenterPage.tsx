/**
 * AI Ustoz (Sprint 88) — minimal real chat UI for the actual backend
 * contract (POST /ai/chats, GET /ai/chats/{id}, POST
 * /ai/chats/{id}/messages). Deliberately NOT a redesign of the whole AI
 * Center: no file attachments, no multi-chat switcher, no streaming (the
 * backend returns one complete response per request, never pretend
 * otherwise) — just send a message, see the reply, same conventions as
 * NotificationsPage.tsx (Button/Input from components/ui, Tailwind
 * utility classes, Uzbek "Yuklanmoqda..." loading text).
 *
 * Mounted ONLY under /student (Applicant/Student role) this sprint —
 * /admin/ai stays an untouched PlaceholderPage; no backend admin-AI
 * feature exists to wire it to.
 */
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/layout/ErrorState";
import { useActiveAiChatId, useAiChatHistory, useSendAiMessage } from "@/hooks/useAi";
import { ApiError } from "@/api/client";

const MAX_MESSAGE_LENGTH = 4000; // mirrors backend/app/modules/ai/constants.py — client-side check only, backend is authoritative

export function AiCenterPage() {
  const { chatId, isResolving: isChatResolving, isError: isChatError } = useActiveAiChatId();
  const historyQuery = useAiChatHistory(chatId);
  const sendMessage = useSendAiMessage(chatId);

  const [draft, setDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // jsdom (unit tests) doesn't implement scrollIntoView at all.
    bottomRef.current?.scrollIntoView?.({ block: "end" });
  }, [historyQuery.data?.history.length]);

  if (isChatError) return <ErrorState title="AI Ustoz" />;

  const trimmed = draft.trim();
  const isTooLong = draft.length > MAX_MESSAGE_LENGTH;
  const canSend = trimmed.length > 0 && !isTooLong && Boolean(chatId) && !sendMessage.isPending;

  function handleSend() {
    if (!canSend || !chatId) return;
    const content = trimmed;
    sendMessage.mutate(content, {
      onSuccess: () => setDraft(""),
    });
  }

  const sendErrorMessage =
    sendMessage.error instanceof ApiError ? sendMessage.error.message : "Xabar yuborilmadi. Birozdan so'ng qayta urinib ko'ring.";

  return (
    <div className="mx-auto flex h-[calc(100vh-8rem)] max-w-2xl flex-col">
      <h1 className="mb-4 text-xl font-semibold text-foreground">AI Ustoz</h1>

      <div className="flex-1 overflow-y-auto rounded-lg border border-border bg-background p-4">
        {isChatResolving || historyQuery.isLoading ? (
          <p className="text-sm text-foreground/50">Yuklanmoqda...</p>
        ) : historyQuery.isError ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            Suhbat tarixini yuklab bo'lmadi.
            <Button variant="outline" size="sm" className="ml-3" onClick={() => historyQuery.refetch()}>
              Qayta urinish
            </Button>
          </div>
        ) : historyQuery.data && historyQuery.data.history.length > 0 ? (
          <ul className="space-y-3">
            {historyQuery.data.history.map((entry) => (
              <li key={entry.id} className={`flex ${entry.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                    entry.role === "user" ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{entry.message}</p>
                  <p className="mt-1 text-right text-xs opacity-60">{new Date(entry.created_at).toLocaleTimeString()}</p>
                </div>
              </li>
            ))}
            <div ref={bottomRef} />
          </ul>
        ) : (
          <p className="text-sm text-foreground/60">Hali xabarlar yo'q. Birinchi savolingizni yuboring.</p>
        )}
      </div>

      {sendMessage.isError ? (
        <div className="mt-3 flex items-center justify-between rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          <span>{sendErrorMessage}</span>
          <Button variant="outline" size="sm" onClick={() => sendMessage.mutate(trimmed || sendMessage.variables || "")}>
            Qayta urinish
          </Button>
        </div>
      ) : null}

      <div className="mt-3 flex items-end gap-2">
        <div className="flex-1">
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Savolingizni yozing..."
            disabled={isChatResolving || !chatId}
          />
          {isTooLong ? (
            <p className="mt-1 text-xs text-destructive">
              Xabar juda uzun ({draft.length}/{MAX_MESSAGE_LENGTH} belgi).
            </p>
          ) : null}
        </div>
        <Button onClick={handleSend} disabled={!canSend}>
          {sendMessage.isPending ? "..." : "Yuborish"}
        </Button>
      </div>
    </div>
  );
}
