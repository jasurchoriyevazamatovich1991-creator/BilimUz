/**
 * Sprint 74 — the "Tuzilma" (exam configuration) entry point added to
 * each row. Admin/Super Admin only (ExamSection/ExamModule/
 * QuestionGroup endpoints require those roles exclusively — stricter
 * than this page's own canWrite, which also allows Teacher).
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TestsListPage } from "./TestsListPage";
import { testsApi } from "@/api/tests";
import { subjectsApi } from "@/api/subjects";
import { useAuthStore } from "@/store/authStore";

vi.mock("@/api/tests");
vi.mock("@/api/subjects");

const TESTS_PAGE = {
  items: [
    {
      id: "t1", subject_id: null, grade_id: null, topic_id: null, title: "SAT Mock", description: null,
      difficulty: "medium", duration: 60, question_count: 5, passing_score: null,
      shuffle_questions: true, shuffle_answers: true, status: "draft", created_at: "", updated_at: "",
    },
  ],
  meta: { page: 1, per_page: 20, total: 1, total_pages: 1 },
};
const EMPTY_SUBJECTS = { items: [], meta: { page: 1, per_page: 100, total: 0, total_pages: 0 } };

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/admin/tests"]}>
        <Routes>
          <Route path="/admin/tests" element={<TestsListPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("TestsListPage — Sprint 74 'Tuzilma' entry point", () => {
  beforeEach(() => {
    vi.mocked(testsApi.list).mockResolvedValue(TESTS_PAGE);
    vi.mocked(subjectsApi.list).mockResolvedValue(EMPTY_SUBJECTS);
  });

  it("Admin sees the 'Tuzilma' link", async () => {
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
    renderPage();
    await waitFor(() => expect(screen.getByText("SAT Mock")).toBeInTheDocument());
    expect(screen.getByText("Tuzilma")).toBeInTheDocument();
  });

  it("Super Admin sees the 'Tuzilma' link", async () => {
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Super Admin" });
    renderPage();
    await waitFor(() => expect(screen.getByText("SAT Mock")).toBeInTheDocument());
    expect(screen.getByText("Tuzilma")).toBeInTheDocument();
  });

  it("Teacher does NOT see the 'Tuzilma' link (cannot read exam-config endpoints at all)", async () => {
    useAuthStore.getState().setUser({ id: "u2", first_name: "A", last_name: "B", phone: null, email: null, role: "Teacher" });
    renderPage();
    await waitFor(() => expect(screen.getByText("SAT Mock")).toBeInTheDocument());
    expect(screen.queryByText("Tuzilma")).not.toBeInTheDocument();
    // Teacher still gets the existing "Savollar" link and write actions.
    expect(screen.getByRole("button", { name: "Savollar" })).toBeInTheDocument();
  });

  it("clicking 'Tuzilma' navigates to the exam-config route", async () => {
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/admin/tests"]}>
          <Routes>
            <Route path="/admin/tests" element={<TestsListPage />} />
            <Route path="/admin/tests/:testId/exam-config" element={<div>Imtihon tuzilmasi sahifasi</div>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText("SAT Mock")).toBeInTheDocument());
    await userEvent.setup().click(screen.getByText("Tuzilma"));
    await waitFor(() => expect(screen.getByText("Imtihon tuzilmasi sahifasi")).toBeInTheDocument());
  });
});
