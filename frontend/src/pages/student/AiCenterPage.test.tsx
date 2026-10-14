import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AiCenterPage } from "./AiCenterPage";
import { aiApi } from "@/api/ai";
import { ApiError } from "@/api/client";

vi.mock("@/api/ai");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AiCenterPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const EXISTING_CHAT = { id: "chat-1", user_id: "u1", title: null, status: "active", created_at: "2026-01-01T10:00:00Z" };

const EMPTY_HISTORY_DETAIL = { ...EXISTING_CHAT, history: [] };

describe("AiCenterPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a loading state while the chat is being resolved", () => {
    vi.mocked(aiApi.myChats).mockImplementation(() => new Promise(() => {})); // never resolves
    renderPage();
    expect(screen.getByText("Yuklanmoqda...")).toBeInTheDocument();
  });

  it("reuses the user's most recent existing chat instead of creating a new one", async () => {
    vi.mocked(aiApi.myChats).mockResolvedValue({ items: [EXISTING_CHAT], meta: { page: 1, per_page: 1, total: 1, total_pages: 1 } });
    vi.mocked(aiApi.getChat).mockResolvedValue(EMPTY_HISTORY_DETAIL);

    renderPage();

    await waitFor(() => expect(aiApi.getChat).toHaveBeenCalledWith("chat-1"));
    expect(aiApi.startChat).not.toHaveBeenCalled();
  });

  it("starts a new chat when the user has none yet", async () => {
    vi.mocked(aiApi.myChats).mockResolvedValue({ items: [], meta: { page: 1, per_page: 1, total: 0, total_pages: 0 } });
    vi.mocked(aiApi.startChat).mockResolvedValue(EXISTING_CHAT);
    vi.mocked(aiApi.getChat).mockResolvedValue(EMPTY_HISTORY_DETAIL);

    renderPage();

    await waitFor(() => expect(aiApi.startChat).toHaveBeenCalledOnce());
    await waitFor(() => expect(aiApi.getChat).toHaveBeenCalledWith("chat-1"));
  });

  it("shows an empty-conversation message when the chat has no history yet", async () => {
    vi.mocked(aiApi.myChats).mockResolvedValue({ items: [EXISTING_CHAT], meta: { page: 1, per_page: 1, total: 1, total_pages: 1 } });
    vi.mocked(aiApi.getChat).mockResolvedValue(EMPTY_HISTORY_DETAIL);

    renderPage();

    await waitFor(() => expect(screen.getByText("Hali xabarlar yo'q. Birinchi savolingizni yuboring.")).toBeInTheDocument());
  });

  it("renders existing history, both user and assistant messages", async () => {
    vi.mocked(aiApi.myChats).mockResolvedValue({ items: [EXISTING_CHAT], meta: { page: 1, per_page: 1, total: 1, total_pages: 1 } });
    vi.mocked(aiApi.getChat).mockResolvedValue({
      ...EXISTING_CHAT,
      history: [
        { id: "h1", chat_id: "chat-1", role: "user", message: "Salom", created_at: "2026-01-01T10:00:00Z" },
        { id: "h2", chat_id: "chat-1", role: "assistant", message: "Salom! Qalaysiz?", created_at: "2026-01-01T10:00:05Z" },
      ],
    });

    renderPage();

    await waitFor(() => expect(screen.getByText("Salom")).toBeInTheDocument());
    expect(screen.getByText("Salom! Qalaysiz?")).toBeInTheDocument();
  });

  it("sends a message and shows the assistant's reply after success", async () => {
    vi.mocked(aiApi.myChats).mockResolvedValue({ items: [EXISTING_CHAT], meta: { page: 1, per_page: 1, total: 1, total_pages: 1 } });
    vi.mocked(aiApi.getChat).mockResolvedValueOnce(EMPTY_HISTORY_DETAIL).mockResolvedValueOnce({
      ...EXISTING_CHAT,
      history: [
        { id: "h1", chat_id: "chat-1", role: "user", message: "Nyuton qonuni nima?", created_at: "2026-01-01T10:00:00Z" },
        { id: "h2", chat_id: "chat-1", role: "assistant", message: "Bu birinchi qonun...", created_at: "2026-01-01T10:00:05Z" },
      ],
    });
    vi.mocked(aiApi.sendMessage).mockResolvedValue({
      chat_id: "chat-1",
      user_message: { id: "h1", chat_id: "chat-1", role: "user", message: "Nyuton qonuni nima?", created_at: "2026-01-01T10:00:00Z" },
      assistant_message: { id: "h2", chat_id: "chat-1", role: "assistant", message: "Bu birinchi qonun...", created_at: "2026-01-01T10:00:05Z" },
    });

    renderPage();
    await waitFor(() => expect(screen.getByPlaceholderText("Savolingizni yozing...")).not.toBeDisabled());

    fireEvent.change(screen.getByPlaceholderText("Savolingizni yozing..."), { target: { value: "Nyuton qonuni nima?" } });
    fireEvent.click(screen.getByText("Yuborish"));

    await waitFor(() => expect(aiApi.sendMessage).toHaveBeenCalledWith("chat-1", "Nyuton qonuni nima?"));
    await waitFor(() => expect(screen.getByText("Bu birinchi qonun...")).toBeInTheDocument());
  });

  it("clears the draft input after a successful send", async () => {
    vi.mocked(aiApi.myChats).mockResolvedValue({ items: [EXISTING_CHAT], meta: { page: 1, per_page: 1, total: 1, total_pages: 1 } });
    vi.mocked(aiApi.getChat).mockResolvedValue(EMPTY_HISTORY_DETAIL);
    vi.mocked(aiApi.sendMessage).mockResolvedValue({
      chat_id: "chat-1",
      user_message: { id: "h1", chat_id: "chat-1", role: "user", message: "Salom", created_at: "2026-01-01T10:00:00Z" },
      assistant_message: { id: "h2", chat_id: "chat-1", role: "assistant", message: "Salom!", created_at: "2026-01-01T10:00:05Z" },
    });

    renderPage();
    const input = await screen.findByPlaceholderText("Savolingizni yozing...");
    fireEvent.change(input, { target: { value: "Salom" } });
    fireEvent.click(screen.getByText("Yuborish"));

    await waitFor(() => expect(input).toHaveValue(""));
  });

  it("disables sending when the draft exceeds the max message length", async () => {
    vi.mocked(aiApi.myChats).mockResolvedValue({ items: [EXISTING_CHAT], meta: { page: 1, per_page: 1, total: 1, total_pages: 1 } });
    vi.mocked(aiApi.getChat).mockResolvedValue(EMPTY_HISTORY_DETAIL);

    renderPage();
    const input = await screen.findByPlaceholderText("Savolingizni yozing...");
    fireEvent.change(input, { target: { value: "a".repeat(4001) } });

    expect(screen.getByText("Yuborish")).toBeDisabled();
    expect(aiApi.sendMessage).not.toHaveBeenCalled();
  });

  it("does not send an empty or whitespace-only message", async () => {
    vi.mocked(aiApi.myChats).mockResolvedValue({ items: [EXISTING_CHAT], meta: { page: 1, per_page: 1, total: 1, total_pages: 1 } });
    vi.mocked(aiApi.getChat).mockResolvedValue(EMPTY_HISTORY_DETAIL);

    renderPage();
    const input = await screen.findByPlaceholderText("Savolingizni yozing...");
    fireEvent.change(input, { target: { value: "   " } });

    expect(screen.getByText("Yuborish")).toBeDisabled();
  });

  it("shows an inline error with a manual retry option when sending fails, without auto-retrying", async () => {
    vi.mocked(aiApi.myChats).mockResolvedValue({ items: [EXISTING_CHAT], meta: { page: 1, per_page: 1, total: 1, total_pages: 1 } });
    vi.mocked(aiApi.getChat).mockResolvedValue(EMPTY_HISTORY_DETAIL);
    vi.mocked(aiApi.sendMessage).mockRejectedValue(new ApiError("AI provayder hozir band. Birozdan so'ng qayta urining.", null, 429));

    renderPage();
    const input = await screen.findByPlaceholderText("Savolingizni yozing...");
    fireEvent.change(input, { target: { value: "Salom" } });
    fireEvent.click(screen.getByText("Yuborish"));

    await waitFor(() => expect(screen.getByText("AI provayder hozir band. Birozdan so'ng qayta urining.")).toBeInTheDocument());
    // Exactly one attempt so far — no silent auto-retry loop.
    expect(aiApi.sendMessage).toHaveBeenCalledOnce();
    expect(screen.getByText("Qayta urinish")).toBeInTheDocument();
  });

  it("shows ErrorState when the chat itself cannot be resolved", async () => {
    vi.mocked(aiApi.myChats).mockRejectedValue(new Error("network error"));

    renderPage();

    await waitFor(() => expect(screen.getByText("AI Ustoz")).toBeInTheDocument());
  });
});
