import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TeacherSubjectsPage } from "./SubjectsPage";
import { subjectsApi } from "@/api/subjects";

vi.mock("@/api/subjects");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <TeacherSubjectsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("TeacherSubjectsPage — read-only (backend write is Admin/Super Admin only)", () => {
  it("loads and shows a subject on success, with no create/edit/delete controls anywhere", async () => {
    vi.mocked(subjectsApi.list).mockResolvedValue({
      items: [{ id: "s1", name: "Matematika", color: "#4f46e5", icon: null, status: "active", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }],
      meta: { page: 1, per_page: 20, total: 1, total_pages: 1 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Matematika")).toBeInTheDocument());
    expect(screen.queryByText("Qo'shish")).not.toBeInTheDocument();
    expect(screen.queryByText("O'chirish")).not.toBeInTheDocument();
  });

  it("shows an empty state when there are no subjects", async () => {
    vi.mocked(subjectsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Fan topilmadi")).toBeInTheDocument());
  });

  it("shows ErrorState on API failure", async () => {
    vi.mocked(subjectsApi.list).mockRejectedValue(new Error("network error"));
    renderPage();
    await waitFor(() => expect(screen.getByText("Fanlar")).toBeInTheDocument());
  });
});
