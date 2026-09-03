import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StudentTestDetailPage } from "./TestDetailPage";
import { testsApi } from "@/api/tests";
import { attemptsApi } from "@/api/attempts";

vi.mock("@/api/tests");
vi.mock("@/api/attempts");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/student/tests/t1"]}>
        <Routes>
          <Route path="/student/tests/:testId" element={<StudentTestDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const TEST_OUT = {
  id: "t1", subject_id: null, grade_id: null, topic_id: null, title: "Matematika testi", description: null,
  difficulty: "medium", duration: 30, question_count: 10, passing_score: 60,
  shuffle_questions: true, shuffle_answers: true, status: "published",
  created_at: "", updated_at: "",
};

describe("StudentTestDetailPage — approved decision 3 (no duplicate attempt)", () => {
  beforeEach(() => {
    vi.mocked(testsApi.get).mockResolvedValue(TEST_OUT);
  });

  it("shows 'Boshlash' when there is no active attempt", async () => {
    vi.mocked(attemptsApi.listMine).mockResolvedValue({ items: [], meta: { page: 1, per_page: 1, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Boshlash")).toBeInTheDocument());
    expect(screen.queryByText("Davom ettirish")).not.toBeInTheDocument();
  });

  it("shows 'Davom ettirish' instead of 'Boshlash' when an active attempt already exists", async () => {
    vi.mocked(attemptsApi.listMine).mockResolvedValue({
      items: [{ id: "a1", test_id: "t1", status: "in_progress", start_time: "", expires_at: null, finish_time: null }],
      meta: { page: 1, per_page: 1, total: 1, total_pages: 1 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Davom ettirish")).toBeInTheDocument());
    expect(screen.queryByText("Boshlash")).not.toBeInTheDocument();
  });

  it("NEVER calls start() when an active attempt exists, even if the user could click something", async () => {
    vi.mocked(attemptsApi.listMine).mockResolvedValue({
      items: [{ id: "a1", test_id: "t1", status: "in_progress", start_time: "", expires_at: null, finish_time: null }],
      meta: { page: 1, per_page: 1, total: 1, total_pages: 1 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Davom ettirish")).toBeInTheDocument());
    expect(attemptsApi.start).not.toHaveBeenCalled();
  });

  it("displays test metadata from the real TestOut fields only", async () => {
    vi.mocked(attemptsApi.listMine).mockResolvedValue({ items: [], meta: { page: 1, per_page: 1, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Matematika testi")).toBeInTheDocument());
    expect(screen.getByText("10")).toBeInTheDocument(); // question_count
    expect(screen.getByText("30 daqiqa")).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument(); // passing_score
  });
});
