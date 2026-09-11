import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ResultsHistoryPage } from "./ResultsHistoryPage";
import { resultsApi } from "@/api/results";
import { testsApi } from "@/api/tests";

vi.mock("@/api/results");
vi.mock("@/api/tests");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/student/results"]}>
        <Routes>
          <Route path="/student/results" element={<ResultsHistoryPage />} />
          <Route path="/student/results/:resultId" element={<div>RESULT_DETAIL_REACHED</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const MOCK_RESULT = {
  id: "r1", attempt_id: "a1", user_id: "u1", test_id: "t1",
  score: 8, percentage: 80, is_passed: true, status: "final", created_at: "2026-01-01T10:00:00Z",
};

const MOCK_TEST = {
  id: "t1", subject_id: null, grade_id: null, topic_id: null, title: "Matematika testi",
  description: null, difficulty: "medium", duration: 30, question_count: 10, passing_score: 60,
  shuffle_questions: true, shuffle_answers: true, status: "published", created_at: "", updated_at: "",
};

describe("ResultsHistoryPage", () => {
  it("renders real results returned by GET /results/me, including the resolved test title", async () => {
    vi.mocked(resultsApi.list).mockResolvedValue({ items: [MOCK_RESULT], meta: { page: 1, per_page: 20, total: 1, total_pages: 1 } });
    vi.mocked(testsApi.get).mockResolvedValue(MOCK_TEST);
    renderPage();
    await waitFor(() => expect(screen.getByText("Matematika testi")).toBeInTheDocument());
    expect(screen.getByText("8 ball (80%)")).toBeInTheDocument();
    expect(screen.getByText("O'tdingiz")).toBeInTheDocument();
  });

  it("shows an honest empty state, not fake results, when the student has none", async () => {
    vi.mocked(resultsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Hozircha natijalar yo'q.")).toBeInTheDocument());
  });

  it("shows a loading state before data arrives", () => {
    vi.mocked(resultsApi.list).mockImplementation(() => new Promise(() => {}));
    renderPage();
    expect(screen.getByText("Yuklanmoqda...")).toBeInTheDocument();
  });

  it("shows ErrorState on API failure", async () => {
    vi.mocked(resultsApi.list).mockRejectedValue(new Error("network error"));
    renderPage();
    await waitFor(() => expect(screen.getByText("Natijalar")).toBeInTheDocument());
  });

  it("shows real backend pagination controls and calls list() with the next page", async () => {
    vi.mocked(resultsApi.list).mockResolvedValue({
      items: [MOCK_RESULT], meta: { page: 1, per_page: 20, total: 45, total_pages: 3 },
    });
    vi.mocked(testsApi.get).mockResolvedValue(MOCK_TEST);
    renderPage();
    await waitFor(() => expect(screen.getByText("Keyingi")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Keyingi"));
    await waitFor(() =>
      expect(resultsApi.list).toHaveBeenCalledWith(expect.objectContaining({ page: 2 })),
    );
  });

  it("clicking a result navigates to the existing /student/results/:resultId route", async () => {
    vi.mocked(resultsApi.list).mockResolvedValue({ items: [MOCK_RESULT], meta: { page: 1, per_page: 20, total: 1, total_pages: 1 } });
    vi.mocked(testsApi.get).mockResolvedValue(MOCK_TEST);
    renderPage();
    await waitFor(() => expect(screen.getByText("Matematika testi")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Matematika testi"));
    await waitFor(() => expect(screen.getByText("RESULT_DETAIL_REACHED")).toBeInTheDocument());
  });

  it("never fetches all results at once — uses real backend pagination params, not an unbounded per_page", async () => {
    vi.mocked(resultsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() =>
      expect(resultsApi.list).toHaveBeenCalledWith(expect.objectContaining({ page: 1, per_page: 20 })),
    );
  });
});
