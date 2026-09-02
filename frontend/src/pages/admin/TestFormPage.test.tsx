import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TestFormPage } from "./TestFormPage";
import { testsApi } from "@/api/tests";
import { subjectsApi } from "@/api/subjects";
import { gradesApi } from "@/api/grades";
import { topicsApi } from "@/api/topics";
import { useAuthStore } from "@/store/authStore";

vi.mock("@/api/tests");
vi.mock("@/api/subjects");
vi.mock("@/api/grades");
vi.mock("@/api/topics");

function renderEditPage(testId = "t1") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/admin/tests/${testId}`]}>
        <Routes>
          <Route path="/admin/tests/:testId" element={<TestFormPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const EMPTY_PAGE = { items: [], meta: { page: 1, per_page: 100, total: 0, total_pages: 0 } };

describe("TestFormPage — no Archive action (approved decision 2, no such endpoint)", () => {
  beforeEach(() => {
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
    vi.mocked(subjectsApi.list).mockResolvedValue(EMPTY_PAGE);
    vi.mocked(gradesApi.list).mockResolvedValue(EMPTY_PAGE);
    vi.mocked(topicsApi.list).mockResolvedValue(EMPTY_PAGE);
  });

  it("never renders an Archive button, even for a published test", async () => {
    vi.mocked(testsApi.get).mockResolvedValue({
      id: "t1", subject_id: null, grade_id: null, topic_id: null, title: "Test 1", description: null,
      difficulty: "medium", duration: 60, question_count: 5, passing_score: null,
      shuffle_questions: true, shuffle_answers: true, status: "published",
      created_at: "", updated_at: "",
    });
    renderEditPage();
    await waitFor(() => expect(screen.getByDisplayValue("Test 1")).toBeInTheDocument());
    expect(screen.queryByText(/arxiv/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Archive")).not.toBeInTheDocument();
  });

  it("shows Publish only for a draft test with at least one question", async () => {
    vi.mocked(testsApi.get).mockResolvedValue({
      id: "t1", subject_id: null, grade_id: null, topic_id: null, title: "Test 1", description: null,
      difficulty: "medium", duration: 60, question_count: 3, passing_score: null,
      shuffle_questions: true, shuffle_answers: true, status: "draft",
      created_at: "", updated_at: "",
    });
    renderEditPage();
    await waitFor(() => expect(screen.getByDisplayValue("Test 1")).toBeInTheDocument());
    expect(screen.getByText("E'lon qilish")).toBeInTheDocument();
  });

  it("hides Publish for a draft test with zero questions (matches backend precondition)", async () => {
    vi.mocked(testsApi.get).mockResolvedValue({
      id: "t1", subject_id: null, grade_id: null, topic_id: null, title: "Test 1", description: null,
      difficulty: "medium", duration: 60, question_count: 0, passing_score: null,
      shuffle_questions: true, shuffle_answers: true, status: "draft",
      created_at: "", updated_at: "",
    });
    renderEditPage();
    await waitFor(() => expect(screen.getByDisplayValue("Test 1")).toBeInTheDocument());
    expect(screen.queryByText("E'lon qilish")).not.toBeInTheDocument();
  });

  it("hides Publish for an already-published test", async () => {
    vi.mocked(testsApi.get).mockResolvedValue({
      id: "t1", subject_id: null, grade_id: null, topic_id: null, title: "Test 1", description: null,
      difficulty: "medium", duration: 60, question_count: 5, passing_score: null,
      shuffle_questions: true, shuffle_answers: true, status: "published",
      created_at: "", updated_at: "",
    });
    renderEditPage();
    await waitFor(() => expect(screen.getByDisplayValue("Test 1")).toBeInTheDocument());
    expect(screen.queryByText("E'lon qilish")).not.toBeInTheDocument();
  });
});
