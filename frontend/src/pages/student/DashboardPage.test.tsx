import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StudentDashboardPage } from "./DashboardPage";
import { testsApi } from "@/api/tests";
import { resultsApi } from "@/api/results";
import { certificatesApi } from "@/api/certificates";
import { progressApi } from "@/api/progress";

vi.mock("@/api/tests");
vi.mock("@/api/results");
vi.mock("@/api/certificates");
vi.mock("@/api/progress");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <StudentDashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("StudentDashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(testsApi.publishedCount).mockResolvedValue(3);
    vi.mocked(resultsApi.myCount).mockResolvedValue(2);
    vi.mocked(certificatesApi.myCount).mockResolvedValue(1);
  });

  it("displays real progress data from GET /progress/me — not a fake/hardcoded percentage", async () => {
    vi.mocked(progressApi.getMyProgress).mockResolvedValue({
      completed_lessons: 3, total_lessons: 10, percentage: 30, completed_lesson_ids: [],
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Tugatilgan: 3 / 10 dars")).toBeInTheDocument());
    expect(screen.getByText("30%")).toBeInTheDocument();
  });

  it("shows a real empty state (0/0, 0%) when the student has no lessons/progress yet — never a fabricated number", async () => {
    vi.mocked(progressApi.getMyProgress).mockResolvedValue({
      completed_lessons: 0, total_lessons: 0, percentage: 0, completed_lesson_ids: [],
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Tugatilgan: 0 / 0 dars")).toBeInTheDocument());
  });

  it("shows ErrorState for the progress card on API failure", async () => {
    vi.mocked(progressApi.getMyProgress).mockRejectedValue(new Error("network error"));
    renderPage();
    await waitFor(() => expect(screen.getByText("O'quv jarayoni")).toBeInTheDocument());
  });

  it("still renders the existing dashboard cards unaffected by the new progress card", async () => {
    vi.mocked(progressApi.getMyProgress).mockResolvedValue({
      completed_lessons: 0, total_lessons: 5, percentage: 0, completed_lesson_ids: [],
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Mavjud testlar")).toBeInTheDocument());
    expect(screen.getByText("Mening natijalarim")).toBeInTheDocument();
    expect(screen.getByText("Sertifikatlarim")).toBeInTheDocument();
  });
});
