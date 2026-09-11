import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StudentSubjectGradeTopicsPage } from "./SubjectGradeTopicsPage";
import { subjectsApi } from "@/api/subjects";
import { gradesApi } from "@/api/grades";
import { topicsApi } from "@/api/topics";

vi.mock("@/api/subjects");
vi.mock("@/api/grades");
vi.mock("@/api/topics");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/student/subjects/s1/grades/g1/topics"]}>
        <Routes>
          <Route path="/student/subjects/:subjectId/grades/:gradeId/topics" element={<StudentSubjectGradeTopicsPage />} />
          <Route path="/student/topics/:topicId/lessons" element={<div>LESSONS_REACHED</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const MOCK_TOPIC = {
  id: "t1", subject_id: "s1", grade_id: "g1", title: "Kasrlar", description: "Kasrlar haqida",
  order_number: 1, status: "active", created_at: "", updated_at: "",
};

describe("StudentSubjectGradeTopicsPage", () => {
  beforeEach(() => {
    vi.mocked(subjectsApi.get).mockResolvedValue({ id: "s1", name: "Matematika", icon: null, color: null, status: "active", created_at: "", updated_at: "" });
    vi.mocked(gradesApi.get).mockResolvedValue({ id: "g1", name: "5-sinf", status: "active", created_at: "", updated_at: "" });
  });

  it("queries topics filtered by BOTH subject_id and grade_id (the real filtering point)", async () => {
    vi.mocked(topicsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 100, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() =>
      expect(topicsApi.list).toHaveBeenCalledWith(expect.objectContaining({ subject_id: "s1", grade_id: "g1", status: "active" })),
    );
  });

  it("loads and shows a topic on success", async () => {
    vi.mocked(topicsApi.list).mockResolvedValue({ items: [MOCK_TOPIC], meta: { page: 1, per_page: 100, total: 1, total_pages: 1 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Kasrlar")).toBeInTheDocument());
  });

  it("navigates to the lessons step when a topic is clicked", async () => {
    vi.mocked(topicsApi.list).mockResolvedValue({ items: [MOCK_TOPIC], meta: { page: 1, per_page: 100, total: 1, total_pages: 1 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Kasrlar")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Kasrlar"));
    await waitFor(() => expect(screen.getByText("LESSONS_REACHED")).toBeInTheDocument());
  });

  it("shows an empty state when there are no topics for this subject+grade", async () => {
    vi.mocked(topicsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 100, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Bu fan va sinf uchun hozircha mavzular mavjud emas.")).toBeInTheDocument());
  });
});
