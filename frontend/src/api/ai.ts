/**
 * AI Center API wrapper — verified against the real backend contract
 * (backend/app/modules/ai/router.py + schemas.py, Sprint 88). Every call
 * requires authentication (handled by httpClient's interceptor, same as
 * every other api/*.ts module).
 *
 * NOTE: `startChat`'s optional `title` is sent as a QUERY param, not a
 * JSON body field — the backend endpoint declares it as a plain
 * `title: str | None = None` function parameter (no Pydantic body
 * model), which FastAPI binds from the query string regardless of HTTP
 * method. Confirmed by reading router.py directly, not assumed.
 */
import { httpClient, unwrap } from "./client";

export interface RecommendationOut {
  id: string;
  text: string;
}

export interface ChatOut {
  id: string;
  user_id: string;
  title: string | null;
  status: string;
  created_at: string;
}

export interface HistoryEntryOut {
  id: string;
  chat_id: string;
  role: "user" | "assistant";
  message: string;
  created_at: string;
}

export interface ChatDetailOut extends ChatOut {
  history: HistoryEntryOut[];
}

export interface MessageResponseOut {
  chat_id: string;
  user_message: HistoryEntryOut;
  assistant_message: HistoryEntryOut;
}

export interface ChatListOut {
  items: ChatOut[];
  meta: { page: number; per_page: number; total: number; total_pages: number };
}

export const aiApi = {
  myRecommendations: () => unwrap<RecommendationOut[]>(httpClient.get("/ai/recommendations/me")),

  myChats: (page = 1, perPage = 1) =>
    unwrap<ChatListOut>(httpClient.get("/ai/chats/me", { params: { page, per_page: perPage } })),

  startChat: (title?: string) =>
    unwrap<ChatOut>(httpClient.post("/ai/chats", null, { params: title ? { title } : undefined })),

  getChat: (chatId: string) => unwrap<ChatDetailOut>(httpClient.get(`/ai/chats/${chatId}`)),

  sendMessage: (chatId: string, content: string) =>
    unwrap<MessageResponseOut>(httpClient.post(`/ai/chats/${chatId}/messages`, { content })),
};
