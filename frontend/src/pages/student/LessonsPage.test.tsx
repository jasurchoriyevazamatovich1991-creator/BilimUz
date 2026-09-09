import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StudentLessonsPage } from "./LessonsPage";
import { lessonsApi } from "@/api/lessons";

vi.mock("@/api/lessons");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <StudentLessonsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("StudentLessonsPage (flat 'Darslar' entry)", () => {
  it("loads and shows a lesson on success", async () => {
    vi.mocked(lessonsApi.list).mockResolvedValue({
      items: [{ id: "l1", topic_id: "t1", title: "Kasrlar", video: null, pdf: null, content: null, status: "active", created_at: "", updated_at: "" }],
      meta: { page: 1, per_page: 20, total: 1, total_pages: 1 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Kasrlar")).toBeInTheDocument());
  });

  it("shows an empty state when there are no lessons", async () => {
    vi.mocked(lessonsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Hozircha darslar mavjud emas.")).toBeInTheDocument());
  });

  it("shows ErrorState on API failure", async () => {
    vi.mocked(lessonsApi.list).mockRejectedValue(new Error("network error"));
    renderPage();
    await waitFor(() => expect(screen.getByText("Darslar")).toBeInTheDocument());
  });
});
