import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LessonFormPage } from "./LessonFormPage";
import { lessonsApi } from "@/api/lessons";
import { topicsApi } from "@/api/topics";
import { useAuthStore } from "@/store/authStore";

vi.mock("@/api/lessons");
vi.mock("@/api/topics");

function renderEditPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/admin/lessons/l1"]}>
        <Routes>
          <Route path="/admin/lessons/:lessonId" element={<LessonFormPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LessonFormPage", () => {
  beforeEach(() => {
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Teacher" });
    vi.mocked(topicsApi.list).mockResolvedValue({
      items: [{ id: "t1", subject_id: "s1", grade_id: null, title: "1-mavzu", description: null, order_number: 1, status: "active", created_at: "", updated_at: "" }],
      meta: { page: 1, per_page: 100, total: 1, total_pages: 1 },
    });
  });

  it("approved decision 4: topic renders as plain read-only text, not a select, in edit mode", async () => {
    vi.mocked(lessonsApi.get).mockResolvedValue({
      id: "l1", topic_id: "t1", title: "Kirish", video: "https://x.com/v", pdf: null, content: null,
      status: "active", created_at: "", updated_at: "",
    });
    renderEditPage();
    await waitFor(() => expect(screen.getByText("1-mavzu")).toBeInTheDocument());
    expect(screen.queryByRole("combobox", { name: /mavzu/i })).not.toBeInTheDocument();
    expect(screen.getByText(/o'zgartirilmaydi/i)).toBeInTheDocument();
  });

  it("approved decision 3: submit is never blocked, but shows the exact required message when video/pdf/content are all empty", async () => {
    vi.mocked(lessonsApi.get).mockResolvedValue({
      id: "l1", topic_id: "t1", title: "Kirish", video: null, pdf: null, content: null,
      status: "active", created_at: "", updated_at: "",
    });
    renderEditPage();
    await waitFor(() => expect(screen.getByText("1-mavzu")).toBeInTheDocument());

    const submitButton = screen.getByRole("button", { name: "Saqlash" });
    expect(submitButton).toBeEnabled(); // never disabled, per approved decision 3

    fireEvent.click(submitButton);
    expect(await screen.findByText("Video, PDF yoki matndan kamida bittasini kiriting.")).toBeInTheDocument();
    expect(lessonsApi.update).not.toHaveBeenCalled(); // no malformed request reaches the backend
  });

  it("submits successfully when at least the content field is filled", async () => {
    vi.mocked(lessonsApi.get).mockResolvedValue({
      id: "l1", topic_id: "t1", title: "Kirish", video: null, pdf: null, content: "Matn bor",
      status: "active", created_at: "", updated_at: "",
    });
    vi.mocked(lessonsApi.update).mockResolvedValue({
      id: "l1", topic_id: "t1", title: "Kirish", video: null, pdf: null, content: "Matn bor",
      status: "active", created_at: "", updated_at: "",
    });
    renderEditPage();
    await waitFor(() => expect(screen.getByText("1-mavzu")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Saqlash" }));
    await waitFor(() => expect(lessonsApi.update).toHaveBeenCalledOnce());
  });

  it("video and pdf inputs use type='url' (approved decision 2, native browser validation)", async () => {
    vi.mocked(lessonsApi.get).mockResolvedValue({
      id: "l1", topic_id: "t1", title: "Kirish", video: null, pdf: null, content: "x",
      status: "active", created_at: "", updated_at: "",
    });
    renderEditPage();
    await waitFor(() => expect(screen.getByText("1-mavzu")).toBeInTheDocument());
    expect(screen.getByLabelText(/video url/i)).toHaveAttribute("type", "url");
    expect(screen.getByLabelText(/pdf url/i)).toHaveAttribute("type", "url");
  });
});
