import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LessonDetailPage } from "./LessonDetailPage";
import { lessonsApi } from "@/api/lessons";
import { testsApi } from "@/api/tests";

vi.mock("@/api/lessons");
vi.mock("@/api/tests");

function renderPage(lessonId = "l1") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/student/lessons/${lessonId}`]}>
        <Routes>
          <Route path="/student/lessons/:lessonId" element={<LessonDetailPage />} />
          <Route path="/student/tests/:testId" element={<div>TEST_DETAIL_REACHED</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const MOCK_LESSON = {
  id: "l1", topic_id: "t1", title: "Kasrlarni qo'shish", video: "https://youtube.com/watch?v=abc",
  pdf: null, content: "Bu darsda kasrlarni qanday qo'shishni o'rganamiz.", status: "active", created_at: "", updated_at: "",
};

describe("LessonDetailPage", () => {
  it("shows the video as a plain safe link, NOT an embedded player (explicit Sprint 27 scope boundary)", async () => {
    vi.mocked(lessonsApi.get).mockResolvedValue(MOCK_LESSON);
    vi.mocked(testsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Kasrlarni qo'shish")).toBeInTheDocument());
    const link = screen.getByText("https://youtube.com/watch?v=abc");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "https://youtube.com/watch?v=abc");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    // No <video>, <iframe>, or YouTube-embed element anywhere.
    expect(document.querySelector("video")).not.toBeInTheDocument();
    expect(document.querySelector("iframe")).not.toBeInTheDocument();
  });

  it("shows the lesson's content text", async () => {
    vi.mocked(lessonsApi.get).mockResolvedValue(MOCK_LESSON);
    vi.mocked(testsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() => expect(screen.getByText(/Bu darsda kasrlarni/)).toBeInTheDocument());
  });

  it("looks up related tests via the lesson's topic_id, not an invented lesson_id", async () => {
    vi.mocked(lessonsApi.get).mockResolvedValue(MOCK_LESSON);
    vi.mocked(testsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() =>
      expect(testsApi.list).toHaveBeenCalledWith(expect.objectContaining({ topic_id: "t1", status: "published" })),
    );
  });

  it("shows a 'Testni boshlash' link for a related published test and navigates into the existing Sprint 20 flow", async () => {
    vi.mocked(lessonsApi.get).mockResolvedValue(MOCK_LESSON);
    vi.mocked(testsApi.list).mockResolvedValue({
      items: [{
        id: "test1", subject_id: null, grade_id: null, topic_id: "t1", title: "Kasrlar testi", description: null,
        difficulty: "medium", duration: 30, question_count: 10, passing_score: 60,
        shuffle_questions: true, shuffle_answers: true, status: "published", created_at: "", updated_at: "",
      }],
      meta: { page: 1, per_page: 20, total: 1, total_pages: 1 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Kasrlar testi")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Kasrlar testi"));
    await waitFor(() => expect(screen.getByText("TEST_DETAIL_REACHED")).toBeInTheDocument());
  });

  it("shows no test section at all when there are no related tests (honest empty, not an error)", async () => {
    vi.mocked(lessonsApi.get).mockResolvedValue(MOCK_LESSON);
    vi.mocked(testsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Kasrlarni qo'shish")).toBeInTheDocument());
    expect(screen.queryByText("Test")).not.toBeInTheDocument();
  });

  it("shows ErrorState on API failure", async () => {
    vi.mocked(lessonsApi.get).mockRejectedValue(new Error("network error"));
    renderPage();
    await waitFor(() => expect(screen.getByText("Dars")).toBeInTheDocument());
  });
});
