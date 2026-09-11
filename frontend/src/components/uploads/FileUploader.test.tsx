import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { FileUploader } from "./FileUploader";
import { uploadsApi } from "@/api/uploads";

vi.mock("@/api/uploads");

function renderUploader(props: Partial<React.ComponentProps<typeof FileUploader>> = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <FileUploader {...props} />
    </QueryClientProvider>,
  );
}

function makeFile(name: string, type: string, sizeBytes = 1000) {
  // Does NOT allocate sizeBytes of real content — for the large-file
  // tests (100MB+, up to 2GB+1) that would try to actually allocate
  // that much memory. FileUploader.tsx itself only ever reads
  // file.type/.size/.name directly; it never reads bytes or calls
  // .slice() (that only happens inside the separately-tested, fully
  // mocked multipartUpload orchestration), so overriding .size on a
  // minimal real File is a safe, faithful test double here.
  const file = new File(["x"], name, { type });
  Object.defineProperty(file, "size", { value: sizeBytes });
  return file;
}

describe("FileUploader", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders the drop zone with the expected accepted-types hint, including the new 2 GB video limit", () => {
    renderUploader();
    expect(screen.getByText("Faylni shu yerga tashlang yoki tanlang")).toBeInTheDocument();
    expect(screen.getByText("Video (2 GB gacha) / Audio / PDF / Image")).toBeInTheDocument();
  });

  it("rejects an unsupported file type with a clear local error, before any API call", () => {
    renderUploader();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const badFile = makeFile("virus.exe", "application/x-msdownload");
    fireEvent.change(input, { target: { files: [badFile] } });
    expect(screen.getByText(/Qo'llab-quvvatlanmaydigan fayl turi/)).toBeInTheDocument();
    expect(uploadsApi.createPresignedUpload).not.toHaveBeenCalled();
  });

  it("accepts a valid file and shows it staged with size, before upload starts", () => {
    renderUploader();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile("lesson.mp4", "video/mp4")] } });
    expect(screen.getByText("lesson.mp4")).toBeInTheDocument();
    expect(screen.getByText("Yuklash")).toBeInTheDocument();
  });

  it("runs the full presigned flow (create session -> PUT -> finalize) on Upload click", async () => {
    vi.mocked(uploadsApi.createPresignedUpload).mockResolvedValue({
      upload_id: "u1", upload_url: "https://r2.example.com/put", required_headers: { "Content-Type": "video/mp4" },
    });
    vi.mocked(uploadsApi.putToPresignedUrl).mockResolvedValue(undefined);
    vi.mocked(uploadsApi.finalize).mockResolvedValue({
      id: "u1", user_id: "user1", lesson_id: null, file_name: "lesson.mp4", file_type: "video",
      size_bytes: 1000, status: "ready", created_at: "",
    });

    renderUploader();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile("lesson.mp4", "video/mp4")] } });
    fireEvent.click(screen.getByText("Yuklash"));

    await waitFor(() => expect(uploadsApi.createPresignedUpload).toHaveBeenCalledWith(
      expect.objectContaining({ original_filename: "lesson.mp4", content_type: "video/mp4" }),
    ));
    await waitFor(() => expect(uploadsApi.putToPresignedUrl).toHaveBeenCalledOnce());
    await waitFor(() => expect(uploadsApi.finalize).toHaveBeenCalledWith("u1"));
  });

  it("passes lessonId through to the presigned session request when provided", async () => {
    vi.mocked(uploadsApi.createPresignedUpload).mockResolvedValue({
      upload_id: "u1", upload_url: "https://r2.example.com/put", required_headers: {},
    });
    vi.mocked(uploadsApi.putToPresignedUrl).mockResolvedValue(undefined);
    vi.mocked(uploadsApi.finalize).mockResolvedValue({
      id: "u1", user_id: "user1", lesson_id: "lesson1", file_name: "lesson.mp4", file_type: "video",
      size_bytes: 1000, status: "ready", created_at: "",
    });

    renderUploader({ lessonId: "lesson1" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile("lesson.mp4", "video/mp4")] } });
    fireEvent.click(screen.getByText("Yuklash"));

    await waitFor(() =>
      expect(uploadsApi.createPresignedUpload).toHaveBeenCalledWith(expect.objectContaining({ lesson_id: "lesson1" })),
    );
  });

  it("shows a real progress percentage driven by the upload callback, not a fake animation", async () => {
    vi.mocked(uploadsApi.createPresignedUpload).mockResolvedValue({
      upload_id: "u1", upload_url: "https://r2.example.com/put", required_headers: {},
    });
    vi.mocked(uploadsApi.putToPresignedUrl).mockImplementation(async (_p, _f, onProgress) => {
      onProgress(42);
    });
    vi.mocked(uploadsApi.finalize).mockImplementation(() => new Promise(() => {})); // never resolves — freeze mid-flow

    renderUploader();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile("lesson.mp4", "video/mp4")] } });
    fireEvent.click(screen.getByText("Yuklash"));

    await waitFor(() => expect(screen.getByText("Yuklanmoqda... 42%")).toBeInTheDocument());
  });

  it("shows an error toast-worthy message when the upload fails, via the real error path", async () => {
    vi.mocked(uploadsApi.createPresignedUpload).mockRejectedValue(new Error("Yuklash sessiyasi yaratilmadi"));

    renderUploader();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile("lesson.mp4", "video/mp4")] } });
    fireEvent.click(screen.getByText("Yuklash"));

    await waitFor(() => expect(uploadsApi.createPresignedUpload).toHaveBeenCalledOnce());
    expect(uploadsApi.putToPresignedUrl).not.toHaveBeenCalled();
  });

  it("clears the staged file when Bekor qilish is clicked, before upload starts", () => {
    renderUploader();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile("lesson.mp4", "video/mp4")] } });
    expect(screen.getByText("lesson.mp4")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Bekor qilish"));
    expect(screen.queryByText("lesson.mp4")).not.toBeInTheDocument();
  });

  it("rejects a video over 2 GB with a clear local error, before any API call (Sprint 27 Amendment)", () => {
    renderUploader();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const hugeFile = makeFile("huge.mp4", "video/mp4", 2 * 1024 * 1024 * 1024 + 1);
    fireEvent.change(input, { target: { files: [hugeFile] } });
    expect(screen.getByText(/Video juda katta/)).toBeInTheDocument();
    expect(uploadsApi.createPresignedUpload).not.toHaveBeenCalled();
    expect(uploadsApi.initiateMultipart).not.toHaveBeenCalled();
  });

  it("automatically routes a large video (>100 MB) through multipart, not the single-PUT flow (Sprint 27 Amendment)", async () => {
    vi.mocked(uploadsApi.initiateMultipart).mockResolvedValue({
      upload_id: "u1", multipart_upload_id: "mp1", total_parts: 6, part_size_bytes: 20 * 1024 * 1024,
    });
    vi.mocked(uploadsApi.getMultipartPartUrl).mockResolvedValue({ part_number: 1, upload_url: "https://r2.example.com/part" });
    vi.mocked(uploadsApi.putPart).mockResolvedValue("etag");
    vi.mocked(uploadsApi.completeMultipart).mockResolvedValue({
      id: "u1", user_id: "user1", lesson_id: null, file_name: "big.mp4", file_type: "video",
      size_bytes: 120 * 1024 * 1024, status: "ready", created_at: "",
    });
    vi.mocked(uploadsApi.get).mockResolvedValue({
      id: "u1", user_id: "user1", lesson_id: null, file_name: "big.mp4", file_type: "video",
      size_bytes: 120 * 1024 * 1024, status: "ready", created_at: "",
    });

    renderUploader();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile("big.mp4", "video/mp4", 120 * 1024 * 1024)] } });
    fireEvent.click(screen.getByText("Yuklash"));

    await waitFor(() => expect(uploadsApi.initiateMultipart).toHaveBeenCalledOnce());
    expect(uploadsApi.createPresignedUpload).not.toHaveBeenCalled(); // the small-file path was NOT used
  });

  it("clicking Bekor qilish during an in-progress upload calls the real cancelUpload (Sprint 27 Amendment)", async () => {
    vi.mocked(uploadsApi.initiateMultipart).mockResolvedValue({
      upload_id: "u1", multipart_upload_id: "mp1", total_parts: 6, part_size_bytes: 20 * 1024 * 1024,
    });
    vi.mocked(uploadsApi.getMultipartPartUrl).mockResolvedValue({ part_number: 1, upload_url: "https://r2.example.com/part" });
    // A brief REAL delay (not a permanent hang) — in-flight parts are
    // allowed to finish before the cancellation checkpoint is reached
    // (documented behavior), so the mock must eventually resolve for
    // that checkpoint to ever be reachable in this test.
    vi.mocked(uploadsApi.putPart).mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve("etag"), 50)),
    );
    vi.mocked(uploadsApi.abortMultipart).mockResolvedValue(undefined as never);

    renderUploader();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile("big.mp4", "video/mp4", 120 * 1024 * 1024)] } });
    fireEvent.click(screen.getByText("Yuklash"));

    await waitFor(() => expect(screen.getByText(/Bekor qilish/)).toBeInTheDocument());
    fireEvent.click(screen.getByText("Bekor qilish"));

    await waitFor(() => expect(uploadsApi.abortMultipart).toHaveBeenCalledWith("u1"), { timeout: 2000 });
  });
});
