import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AdminFilesPage } from "./FilesPage";
import { uploadsApi } from "@/api/uploads";

vi.mock("@/api/uploads");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AdminFilesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const MOCK_FILE = {
  id: "u1", user_id: "admin1", lesson_id: null, file_name: "lesson-video.mp4", file_type: "video",
  size_bytes: 5 * 1024 * 1024, status: "ready", created_at: "",
};

describe("AdminFilesPage", () => {
  it("loads and shows a file row on success", async () => {
    vi.mocked(uploadsApi.listMine).mockResolvedValue({ items: [MOCK_FILE], meta: { page: 1, per_page: 20, total: 1, total_pages: 1 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("lesson-video.mp4")).toBeInTheDocument());
    expect(screen.getByText("5.0 MB")).toBeInTheDocument();
  });

  it("shows an empty state when there are no files", async () => {
    vi.mocked(uploadsApi.listMine).mockResolvedValue({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Hozircha fayl yo'q")).toBeInTheDocument());
  });

  it("shows ErrorState on API failure", async () => {
    vi.mocked(uploadsApi.listMine).mockRejectedValue(new Error("network error"));
    renderPage();
    await waitFor(() => expect(screen.getByText("Fayllar")).toBeInTheDocument());
  });

  it("deletes a file via ConfirmDialog, not a raw browser confirm", async () => {
    vi.mocked(uploadsApi.listMine).mockResolvedValue({ items: [MOCK_FILE], meta: { page: 1, per_page: 20, total: 1, total_pages: 1 } });
    vi.mocked(uploadsApi.remove).mockResolvedValue(undefined as never);
    renderPage();
    await waitFor(() => expect(screen.getByText("lesson-video.mp4")).toBeInTheDocument());

    fireEvent.click(screen.getByText("O'chirish"));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "O'chirish" }));
    await waitFor(() => expect(uploadsApi.remove).toHaveBeenCalledWith("u1"));
  });

  it("opens a signed view URL in a new tab when 'Ko'rish' is clicked for a ready file", async () => {
    vi.mocked(uploadsApi.listMine).mockResolvedValue({ items: [MOCK_FILE], meta: { page: 1, per_page: 20, total: 1, total_pages: 1 } });
    vi.mocked(uploadsApi.getViewUrl).mockResolvedValue({ view_url: "https://r2.example.com/signed-get" });
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);

    renderPage();
    await waitFor(() => expect(screen.getByText("lesson-video.mp4")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Ko'rish"));

    await waitFor(() => expect(uploadsApi.getViewUrl).toHaveBeenCalledWith("u1"));
    await waitFor(() => expect(openSpy).toHaveBeenCalledWith("https://r2.example.com/signed-get", "_blank", "noopener,noreferrer"));
    openSpy.mockRestore();
  });

  it("does not show 'Ko'rish' for a file that isn't ready yet (still pending)", async () => {
    vi.mocked(uploadsApi.listMine).mockResolvedValue({
      items: [{ ...MOCK_FILE, status: "pending" }], meta: { page: 1, per_page: 20, total: 1, total_pages: 1 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("lesson-video.mp4")).toBeInTheDocument());
    expect(screen.queryByText("Ko'rish")).not.toBeInTheDocument();
  });
});
