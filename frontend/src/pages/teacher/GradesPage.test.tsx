import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TeacherGradesPage } from "./GradesPage";
import { gradesApi } from "@/api/grades";

vi.mock("@/api/grades");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <TeacherGradesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("TeacherGradesPage — read-only (backend write is Admin/Super Admin only)", () => {
  it("loads and shows a grade on success, with no write controls", async () => {
    vi.mocked(gradesApi.list).mockResolvedValue({
      items: [{ id: "g1", name: "5-sinf", status: "active", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }],
      meta: { page: 1, per_page: 20, total: 1, total_pages: 1 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("5-sinf")).toBeInTheDocument());
    expect(screen.queryByText("Qo'shish")).not.toBeInTheDocument();
  });

  it("shows an empty state when there are no grades", async () => {
    vi.mocked(gradesApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Sinf topilmadi")).toBeInTheDocument());
  });
});
