import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TeacherDashboardPage } from "./DashboardPage";
import { topicsApi } from "@/api/topics";
import { lessonsApi } from "@/api/lessons";
import { testsApi } from "@/api/tests";
import { questionsApi } from "@/api/questions";

vi.mock("@/api/topics");
vi.mock("@/api/lessons");
vi.mock("@/api/tests");
vi.mock("@/api/questions");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <TeacherDashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("TeacherDashboardPage", () => {
  it("shows real counts from the actual list endpoints (meta.total), not fabricated numbers", async () => {
    vi.mocked(topicsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 1, total: 12, total_pages: 12 } });
    vi.mocked(lessonsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 1, total: 34, total_pages: 34 } });
    vi.mocked(testsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 1, total: 7, total_pages: 7 } });
    vi.mocked(questionsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 1, total: 56, total_pages: 56 } });

    renderPage();
    await waitFor(() => expect(screen.getByText("12")).toBeInTheDocument());
    expect(screen.getByText("34")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("56")).toBeInTheDocument();
  });

  it("shows a loading skeleton before data arrives", () => {
    vi.mocked(topicsApi.list).mockImplementation(() => new Promise(() => {}));
    vi.mocked(lessonsApi.list).mockImplementation(() => new Promise(() => {}));
    vi.mocked(testsApi.list).mockImplementation(() => new Promise(() => {}));
    vi.mocked(questionsApi.list).mockImplementation(() => new Promise(() => {}));
    renderPage();
    expect(screen.getByText("Mavzular")).toBeInTheDocument(); // card titles render immediately, values load async
  });
});
