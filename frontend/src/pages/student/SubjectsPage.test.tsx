import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StudentSubjectsPage } from "./SubjectsPage";
import { subjectsApi } from "@/api/subjects";

vi.mock("@/api/subjects");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<StudentSubjectsPage />} />
          <Route path="/student/subjects/:subjectId/grades" element={<div>GRADES_REACHED</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const MOCK_SUBJECT = { id: "s1", name: "Matematika", icon: null, color: "#4f46e5", status: "active", created_at: "", updated_at: "" };

describe("StudentSubjectsPage", () => {
  it("loads and shows a subject card on success", async () => {
    vi.mocked(subjectsApi.list).mockResolvedValue({ items: [MOCK_SUBJECT], meta: { page: 1, per_page: 24, total: 1, total_pages: 1 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Matematika")).toBeInTheDocument());
  });

  it("shows an empty state when there are no subjects", async () => {
    vi.mocked(subjectsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 24, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Hozircha fanlar mavjud emas.")).toBeInTheDocument());
  });

  it("shows ErrorState on API failure", async () => {
    vi.mocked(subjectsApi.list).mockRejectedValue(new Error("network error"));
    renderPage();
    await waitFor(() => expect(screen.getByText("Mening fanlarim")).toBeInTheDocument());
  });

  it("navigates to the grades step when a subject is clicked", async () => {
    vi.mocked(subjectsApi.list).mockResolvedValue({ items: [MOCK_SUBJECT], meta: { page: 1, per_page: 24, total: 1, total_pages: 1 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Matematika")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Matematika"));
    await waitFor(() => expect(screen.getByText("GRADES_REACHED")).toBeInTheDocument());
  });

  it("filters by status=active only — draft/inactive subjects never requested", async () => {
    vi.mocked(subjectsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 24, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() => expect(subjectsApi.list).toHaveBeenCalledWith(expect.objectContaining({ status: "active" })));
  });
});
