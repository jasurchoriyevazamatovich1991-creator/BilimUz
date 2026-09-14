import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LessonFormPage } from "./LessonFormPage";
import { lessonsApi } from "@/api/lessons";
import { topicsApi } from "@/api/topics";
import { uploadsApi } from "@/api/uploads";
import { useAuthStore } from "@/store/authStore";

vi.mock("@/api/lessons");
vi.mock("@/api/topics");
vi.mock("@/api/uploads");

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
      id: "l1", topic_id: "t1", title: "Kirish", video: "https://x.com/v", video_upload_id: null, order_number: 0, pdf: null, content: null,
      status: "active", created_at: "", updated_at: "",
    });
    renderEditPage();
    await waitFor(() => expect(screen.getByText("1-mavzu")).toBeInTheDocument());
    expect(screen.queryByRole("combobox", { name: /mavzu/i })).not.toBeInTheDocument();
    expect(screen.getByText(/o'zgartirilmaydi/i)).toBeInTheDocument();
  });

  it("approved decision 3: submit is never blocked, but shows the exact required message when video/pdf/content are all empty", async () => {
    vi.mocked(lessonsApi.get).mockResolvedValue({
      id: "l1", topic_id: "t1", title: "Kirish", video: null, video_upload_id: null, order_number: 0, pdf: null, content: null,
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
      id: "l1", topic_id: "t1", title: "Kirish", video: null, video_upload_id: null, order_number: 0, pdf: null, content: "Matn bor",
      status: "active", created_at: "", updated_at: "",
    });
    vi.mocked(lessonsApi.update).mockResolvedValue({
      id: "l1", topic_id: "t1", title: "Kirish", video: null, video_upload_id: null, order_number: 0, pdf: null, content: "Matn bor",
      status: "active", created_at: "", updated_at: "",
    });
    renderEditPage();
    await waitFor(() => expect(screen.getByText("1-mavzu")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Saqlash" }));
    await waitFor(() => expect(lessonsApi.update).toHaveBeenCalledOnce());
  });

  it("video and pdf inputs use type='url' (approved decision 2, native browser validation)", async () => {
    vi.mocked(lessonsApi.get).mockResolvedValue({
      id: "l1", topic_id: "t1", title: "Kirish", video: null, video_upload_id: null, order_number: 0, pdf: null, content: "x",
      status: "active", created_at: "", updated_at: "",
    });
    renderEditPage();
    await waitFor(() => expect(screen.getByText("1-mavzu")).toBeInTheDocument());
    expect(screen.getByLabelText(/video url/i)).toHaveAttribute("type", "url");
    expect(screen.getByLabelText(/pdf url/i)).toHaveAttribute("type", "url");
  });

  // --- Sprint 35: R2 video upload ---

  it("edit mode: shows the R2 video upload section (real FileUploader)", async () => {
    vi.mocked(lessonsApi.get).mockResolvedValue({
      id: "l1", topic_id: "t1", title: "Kirish", video: null, video_upload_id: null, order_number: 0, pdf: null, content: "x",
      status: "active", created_at: "", updated_at: "",
    });
    renderEditPage();
    await waitFor(() => expect(screen.getByText("1-mavzu")).toBeInTheDocument());
    expect(screen.getByText("Video (R2 orqali yuklash)")).toBeInTheDocument();
  });

  it("shows a confirmation note when an R2 video is already attached", async () => {
    vi.mocked(lessonsApi.get).mockResolvedValue({
      id: "l1", topic_id: "t1", title: "Kirish", video: null, video_upload_id: "u1", order_number: 0, pdf: null, content: "x",
      status: "active", created_at: "", updated_at: "",
    });
    renderEditPage();
    await waitFor(() => expect(screen.getByText(/R2 video yuklangan/)).toBeInTheDocument());
  });

  it("a successful upload calls updateLesson with the new video_upload_id", async () => {
    vi.mocked(lessonsApi.get).mockResolvedValue({
      id: "l1", topic_id: "t1", title: "Kirish", video: null, video_upload_id: null, order_number: 0, pdf: null, content: "x",
      status: "active", created_at: "", updated_at: "",
    });
    vi.mocked(lessonsApi.update).mockResolvedValue({
      id: "l1", topic_id: "t1", title: "Kirish", video: null, video_upload_id: "new-upload-1", order_number: 0, pdf: null, content: "x",
      status: "active", created_at: "", updated_at: "",
    });
    vi.mocked(uploadsApi.createPresignedUpload).mockResolvedValue({
      upload_id: "new-upload-1", upload_url: "https://r2.example.com/put", required_headers: {},
    });
    vi.mocked(uploadsApi.putToPresignedUrl).mockResolvedValue(undefined);
    vi.mocked(uploadsApi.finalize).mockResolvedValue({
      id: "new-upload-1", user_id: "u1", lesson_id: "l1", file_name: "clip.mp4", file_type: "video",
      size_bytes: 1000, status: "ready", created_at: "",
    });

    renderEditPage();
    await waitFor(() => expect(screen.getByText("Video (R2 orqali yuklash)")).toBeInTheDocument());

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["x"], "clip.mp4", { type: "video/mp4" });
    fireEvent.change(fileInput, { target: { files: [file] } });
    fireEvent.click(screen.getByText("Yuklash"));

    await waitFor(() =>
      expect(uploadsApi.createPresignedUpload).toHaveBeenCalledWith(expect.objectContaining({ lesson_id: "l1" })),
    );
    await waitFor(() =>
      expect(lessonsApi.update).toHaveBeenCalledWith("l1", { video_upload_id: "new-upload-1" }),
    );
  });

  // --- Sprint 38: Lesson Ordering ---

  it("shows the order_number input field", async () => {
    vi.mocked(lessonsApi.get).mockResolvedValue({
      id: "l1", topic_id: "t1", title: "Kirish", video: null, video_upload_id: null, pdf: null, content: "x",
      order_number: 2, status: "active", created_at: "", updated_at: "",
    });
    renderEditPage();
    await waitFor(() => expect(screen.getByLabelText(/Tartib raqami/)).toBeInTheDocument());
  });

  it("edit mode: loads the existing order_number into the field", async () => {
    vi.mocked(lessonsApi.get).mockResolvedValue({
      id: "l1", topic_id: "t1", title: "Kirish", video: null, video_upload_id: null, pdf: null, content: "x",
      order_number: 5, status: "active", created_at: "", updated_at: "",
    });
    renderEditPage();
    await waitFor(() => expect(screen.getByLabelText(/Tartib raqami/)).toHaveValue(5));
  });

  it("create mode: leaving order_number empty sends undefined, letting the backend auto-assign", async () => {
    vi.mocked(topicsApi.list).mockResolvedValue({
      items: [{ id: "t1", subject_id: "s1", grade_id: null, title: "1-mavzu", description: null, order_number: 0, status: "active", created_at: "", updated_at: "" }],
      meta: { page: 1, per_page: 100, total: 1, total_pages: 1 },
    });
    vi.mocked(lessonsApi.create).mockResolvedValue({
      id: "new1", topic_id: "t1", title: "Yangi dars", video: null, video_upload_id: null, pdf: null, content: "Matn",
      order_number: 3, status: "active", created_at: "", updated_at: "",
    });
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={["/admin/lessons/new"]}>
          <Routes>
            <Route path="/admin/lessons/new" element={<LessonFormPage />} />
            <Route path="/admin/lessons" element={<div>LESSONS_LIST</div>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByLabelText("Sarlavha")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByRole("option", { name: "1-mavzu" })).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("Mavzu"), { target: { value: "t1" } });
    fireEvent.change(screen.getByLabelText("Sarlavha"), { target: { value: "Yangi dars" } });
    fireEvent.change(screen.getByLabelText("Matn (ixtiyoriy)"), { target: { value: "Matn" } });
    fireEvent.click(screen.getByText("Saqlash"));

    await waitFor(() =>
      expect(lessonsApi.create).toHaveBeenCalledWith(expect.objectContaining({ order_number: undefined })),
    );
  });

  it("edit mode: an explicit order_number value is sent as a number, not a string", async () => {
    vi.mocked(lessonsApi.get).mockResolvedValue({
      id: "l1", topic_id: "t1", title: "Kirish", video: null, video_upload_id: null, pdf: null, content: "x",
      order_number: 2, status: "active", created_at: "", updated_at: "",
    });
    vi.mocked(lessonsApi.update).mockResolvedValue({
      id: "l1", topic_id: "t1", title: "Kirish", video: null, video_upload_id: null, pdf: null, content: "x",
      order_number: 9, status: "active", created_at: "", updated_at: "",
    });
    renderEditPage();
    await waitFor(() => expect(screen.getByLabelText(/Tartib raqami/)).toHaveValue(2));
    fireEvent.change(screen.getByLabelText(/Tartib raqami/), { target: { value: "9" } });
    fireEvent.click(screen.getByText("Saqlash"));

    await waitFor(() =>
      expect(lessonsApi.update).toHaveBeenCalledWith("l1", expect.objectContaining({ order_number: 9 })),
    );
  });
});
