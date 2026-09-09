import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TopicLessonsPage } from "./TopicLessonsPage";
import { topicsApi } from "@/api/topics";
import { lessonsApi } from "@/api/lessons";

vi.mock("@/api/topics");
vi.mock("@/api/lessons");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/student/topics/t1/lessons"]}>
        <Routes>
          <Route path="/student/topics/:topicId/lessons" element={<TopicLessonsPage />} />
          <Route path="/student/lessons/:lessonId" element={<div>LESSON_DETAIL_REACHED</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const MOCK_LESSON = {
  id: "l1", topic_id: "t1", title: "Kasrlarni qo'shish", video: "https://youtube.com/watch?v=abc",
  pdf: null, content: "Kirish matni", status: "active", created_at: "", updated_at: "",
};

describe("TopicLessonsPage", () => {
  beforeEach(() => {
    vi.mocked(topicsApi.get).mockResolvedValue({
      id: "t1", subject_id: "s1", grade_id: "g1", title: "Kasrlar", description: null,
      order_number: 1, status: "active", created_at: "", updated_at: "",
    });
  });

  it("queries lessons filtered by topic_id and status=active", async () => {
    vi.mocked(lessonsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 100, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() =>
      expect(lessonsApi.list).toHaveBeenCalledWith(expect.objectContaining({ topic_id: "t1", status: "active" })),
    );
  });

  it("loads and shows a lesson with a video indicator badge", async () => {
    vi.mocked(lessonsApi.list).mockResolvedValue({ items: [MOCK_LESSON], meta: { page: 1, per_page: 100, total: 1, total_pages: 1 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Kasrlarni qo'shish")).toBeInTheDocument());
    expect(screen.getByText("Video")).toBeInTheDocument();
  });

  it("navigates to the lesson detail page when clicked", async () => {
    vi.mocked(lessonsApi.list).mockResolvedValue({ items: [MOCK_LESSON], meta: { page: 1, per_page: 100, total: 1, total_pages: 1 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Kasrlarni qo'shish")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Kasrlarni qo'shish"));
    await waitFor(() => expect(screen.getByText("LESSON_DETAIL_REACHED")).toBeInTheDocument());
  });

  it("shows an empty state when there are no lessons for this topic", async () => {
    vi.mocked(lessonsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 100, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Bu mavzu uchun hozircha darslar mavjud emas.")).toBeInTheDocument());
  });
});
