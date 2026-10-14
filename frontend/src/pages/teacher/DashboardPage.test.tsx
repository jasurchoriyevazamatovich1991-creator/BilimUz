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

  // Sprint 89 — audit finding: this page previously had no isError
  // handling at all on any of its four widgets, so a failed request
  // rendered DashboardCard's "Ma'lumot yo'q" (no data) branch —
  // identical to a genuinely empty/zero count, with no way to tell
  // them apart. These tests pin the fix (ErrorState per failed widget,
  // the other three still showing their real data).
  it("shows ErrorState for a widget whose request fails, while the others still show real data", async () => {
    vi.mocked(topicsApi.list).mockRejectedValue(new Error("network error"));
    vi.mocked(lessonsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 1, total: 34, total_pages: 34 } });
    vi.mocked(testsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 1, total: 7, total_pages: 7 } });
    vi.mocked(questionsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 1, total: 56, total_pages: 56 } });

    renderPage();
    await waitFor(() => expect(screen.getByText("34")).toBeInTheDocument());
    // ErrorState's own fixed copy (see components/layout/ErrorState.tsx)
    expect(screen.getByText("Yuklab bo'lmadi")).toBeInTheDocument();
    // A failed widget never silently shows "no data" as if it were a
    // real empty state.
    expect(screen.queryByText("Ma'lumot yo'q")).not.toBeInTheDocument();
  });

  it("distinguishes a genuinely empty (zero) count from a failed request", async () => {
    vi.mocked(topicsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 1, total: 0, total_pages: 0 } });
    vi.mocked(lessonsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 1, total: 0, total_pages: 0 } });
    vi.mocked(testsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 1, total: 0, total_pages: 0 } });
    vi.mocked(questionsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 1, total: 0, total_pages: 0 } });

    renderPage();
    await waitFor(() => expect(screen.getAllByText("0")).toHaveLength(4));
    expect(screen.queryByText("Yuklab bo'lmadi")).not.toBeInTheDocument();
  });
});
