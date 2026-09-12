import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LessonDetailPage } from "./LessonDetailPage";
import { lessonsApi } from "@/api/lessons";
import { testsApi } from "@/api/tests";
import { uploadsApi } from "@/api/uploads";

vi.mock("@/api/lessons");
vi.mock("@/api/tests");
vi.mock("@/api/uploads");

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
  id: "l1", topic_id: "t1", title: "Kasrlarni qo'shish", video: "https://youtube.com/watch?v=abc", video_upload_id: null,
  pdf: null, content: "Bu darsda kasrlarni qanday qo'shishni o'rganamiz.", status: "active", created_at: "", updated_at: "",
};

describe("LessonDetailPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("legacy lesson (video_upload_id null): shows the raw video URL as a plain safe link, no embedded player", async () => {
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

  // --- Sprint 35: real R2 video player ---

  it("video_upload_id set: renders a real <video> player using a signed URL, not the raw legacy link", async () => {
    vi.mocked(lessonsApi.get).mockResolvedValue({ ...MOCK_LESSON, video_upload_id: "u1" });
    vi.mocked(testsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 } });
    vi.mocked(uploadsApi.getViewUrl).mockResolvedValue({ view_url: "https://r2.example.com/signed-get" });
    renderPage();
    await waitFor(() => {
      const video = document.querySelector("video");
      expect(video).toBeInTheDocument();
      expect(video).toHaveAttribute("src", "https://r2.example.com/signed-get");
    });
    // The raw legacy video URL text is NOT shown as a link when video_upload_id takes priority.
    expect(screen.queryByText("https://youtube.com/watch?v=abc")).not.toBeInTheDocument();
  });

  it("video_upload_id set: only requests the signed URL for THIS lesson's own upload_id", async () => {
    vi.mocked(lessonsApi.get).mockResolvedValue({ ...MOCK_LESSON, video_upload_id: "u1" });
    vi.mocked(testsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 } });
    vi.mocked(uploadsApi.getViewUrl).mockResolvedValue({ view_url: "https://r2.example.com/signed-get" });
    renderPage();
    await waitFor(() => expect(uploadsApi.getViewUrl).toHaveBeenCalledWith("u1"));
  });

  it("no video at all: does not call getViewUrl (no wasted request) and shows no video section", async () => {
    vi.mocked(lessonsApi.get).mockResolvedValue({ ...MOCK_LESSON, video: null, video_upload_id: null });
    vi.mocked(testsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Kasrlarni qo'shish")).toBeInTheDocument());
    expect(uploadsApi.getViewUrl).not.toHaveBeenCalled();
    expect(document.querySelector("video")).not.toBeInTheDocument();
  });

  it("video player shows ErrorState if the signed URL request fails", async () => {
    vi.mocked(lessonsApi.get).mockResolvedValue({ ...MOCK_LESSON, video_upload_id: "u1" });
    vi.mocked(testsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 } });
    vi.mocked(uploadsApi.getViewUrl).mockRejectedValue(new Error("expired or unauthorized"));
    renderPage();
    await waitFor(() => expect(screen.getByText("Video")).toBeInTheDocument());
  });
});
