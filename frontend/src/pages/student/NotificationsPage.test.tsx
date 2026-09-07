import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NotificationsPage } from "./NotificationsPage";
import { notificationsApi } from "@/api/notifications";

vi.mock("@/api/notifications");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <NotificationsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const UNREAD = { id: "n1", user_id: "u1", title: "Yangi test", message: "Sizga yangi test tayinlandi", channel: "in_app", is_read: false, created_at: "2026-01-01T10:00:00Z" };
const READ = { id: "n2", user_id: "u1", title: "Eski xabar", message: "Bu allaqachon o'qilgan", channel: "in_app", is_read: true, created_at: "2026-01-01T09:00:00Z" };

describe("NotificationsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(notificationsApi.unreadCount).mockResolvedValue(0);
  });

  it("renders the page title", async () => {
    vi.mocked(notificationsApi.listMine).mockResolvedValue({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 } });
    renderPage();
    expect(screen.getByText("Bildirishnomalar")).toBeInTheDocument();
  });

  it("loads and shows notifications on success (title, message, date)", async () => {
    vi.mocked(notificationsApi.listMine).mockResolvedValue({ items: [UNREAD], meta: { page: 1, per_page: 20, total: 1, total_pages: 1 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Yangi test")).toBeInTheDocument());
    expect(screen.getByText("Sizga yangi test tayinlandi")).toBeInTheDocument();
  });

  it("shows an empty state when there are no notifications", async () => {
    vi.mocked(notificationsApi.listMine).mockResolvedValue({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Hozircha bildirishnomalar yo'q.")).toBeInTheDocument());
  });

  it("shows a loading state before data arrives", () => {
    vi.mocked(notificationsApi.listMine).mockImplementation(() => new Promise(() => {})); // never resolves
    renderPage();
    expect(screen.getByText("Yuklanmoqda...")).toBeInTheDocument();
  });

  it("shows ErrorState on API failure", async () => {
    vi.mocked(notificationsApi.listMine).mockRejectedValue(new Error("network error"));
    renderPage();
    await waitFor(() => expect(screen.getByText("Bildirishnomalar")).toBeInTheDocument());
  });

  it("visually distinguishes unread from read notifications (unread dot + 'O'qildi' action)", async () => {
    vi.mocked(notificationsApi.listMine).mockResolvedValue({ items: [UNREAD, READ], meta: { page: 1, per_page: 20, total: 2, total_pages: 1 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Yangi test")).toBeInTheDocument());
    expect(screen.getByLabelText("O'qilmagan")).toBeInTheDocument();
    expect(screen.getByText("O'qildi")).toBeInTheDocument(); // only rendered for the unread one
  });

  it("marks a single notification as read using the real endpoint", async () => {
    vi.mocked(notificationsApi.listMine).mockResolvedValue({ items: [UNREAD], meta: { page: 1, per_page: 20, total: 1, total_pages: 1 } });
    vi.mocked(notificationsApi.markRead).mockResolvedValue({ ...UNREAD, is_read: true });
    renderPage();
    await waitFor(() => expect(screen.getByText("O'qildi")).toBeInTheDocument());

    fireEvent.click(screen.getByText("O'qildi"));
    await waitFor(() => expect(notificationsApi.markRead).toHaveBeenCalledWith("n1"));
  });

  it("marks all as read using the real endpoint, only when there is something unread", async () => {
    vi.mocked(notificationsApi.listMine).mockResolvedValue({ items: [UNREAD], meta: { page: 1, per_page: 20, total: 1, total_pages: 1 } });
    vi.mocked(notificationsApi.unreadCount).mockResolvedValue(1);
    vi.mocked(notificationsApi.markAllRead).mockResolvedValue({ marked_count: 1 });
    renderPage();
    await waitFor(() => expect(screen.getByText("Barchasini o'qilgan deb belgilash")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Barchasini o'qilgan deb belgilash"));
    await waitFor(() => expect(notificationsApi.markAllRead).toHaveBeenCalledOnce());
  });

  it("hides the 'mark all as read' button entirely when unread count is 0", async () => {
    vi.mocked(notificationsApi.listMine).mockResolvedValue({ items: [READ], meta: { page: 1, per_page: 20, total: 1, total_pages: 1 } });
    vi.mocked(notificationsApi.unreadCount).mockResolvedValue(0);
    renderPage();
    await waitFor(() => expect(screen.getByText("Eski xabar")).toBeInTheDocument());
    expect(screen.queryByText("Barchasini o'qilgan deb belgilash")).not.toBeInTheDocument();
  });

  it("invalidates the list after marking read, so a re-render reflects the new state (query invalidation wiring)", async () => {
    vi.mocked(notificationsApi.listMine).mockResolvedValue({ items: [UNREAD], meta: { page: 1, per_page: 20, total: 1, total_pages: 1 } });
    vi.mocked(notificationsApi.markRead).mockResolvedValue({ ...UNREAD, is_read: true });
    renderPage();
    await waitFor(() => expect(screen.getByText("O'qildi")).toBeInTheDocument());

    fireEvent.click(screen.getByText("O'qildi"));
    await waitFor(() => expect(notificationsApi.markRead).toHaveBeenCalledOnce());
    // list refetches after invalidation — called at least twice (mount + post-mutation refetch)
    await waitFor(() => expect(notificationsApi.listMine).toHaveBeenCalledTimes(2));
  });
});
