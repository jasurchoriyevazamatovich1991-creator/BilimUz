import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StudentSubjectGradesPage } from "./SubjectGradesPage";
import { subjectsApi } from "@/api/subjects";
import { gradesApi } from "@/api/grades";

vi.mock("@/api/subjects");
vi.mock("@/api/grades");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/student/subjects/s1/grades"]}>
        <Routes>
          <Route path="/student/subjects/:subjectId/grades" element={<StudentSubjectGradesPage />} />
          <Route path="/student/subjects/:subjectId/grades/:gradeId/topics" element={<div>TOPICS_REACHED</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("StudentSubjectGradesPage", () => {
  it("loads and shows a grade on success, labeled with the subject name", async () => {
    vi.mocked(subjectsApi.get).mockResolvedValue({ id: "s1", name: "Matematika", icon: null, color: null, status: "active", created_at: "", updated_at: "" });
    vi.mocked(gradesApi.list).mockResolvedValue({
      items: [{ id: "g1", name: "5-sinf", status: "active", created_at: "", updated_at: "" }],
      meta: { page: 1, per_page: 100, total: 1, total_pages: 1 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("5-sinf")).toBeInTheDocument());
    expect(screen.getByText("Matematika — sinf tanlang")).toBeInTheDocument();
  });

  it("navigates to the topics step, carrying both subjectId and gradeId, when a grade is clicked", async () => {
    vi.mocked(subjectsApi.get).mockResolvedValue({ id: "s1", name: "Matematika", icon: null, color: null, status: "active", created_at: "", updated_at: "" });
    vi.mocked(gradesApi.list).mockResolvedValue({
      items: [{ id: "g1", name: "5-sinf", status: "active", created_at: "", updated_at: "" }],
      meta: { page: 1, per_page: 100, total: 1, total_pages: 1 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("5-sinf")).toBeInTheDocument());
    fireEvent.click(screen.getByText("5-sinf"));
    await waitFor(() => expect(screen.getByText("TOPICS_REACHED")).toBeInTheDocument());
  });

  it("shows an empty state when there are no grades", async () => {
    vi.mocked(subjectsApi.get).mockResolvedValue({ id: "s1", name: "Matematika", icon: null, color: null, status: "active", created_at: "", updated_at: "" });
    vi.mocked(gradesApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 100, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Hozircha sinflar mavjud emas.")).toBeInTheDocument());
  });
});
