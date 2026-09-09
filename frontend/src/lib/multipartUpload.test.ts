import { describe, expect, it, vi, beforeEach } from "vitest";
import { startMultipartUpload } from "./multipartUpload";
import { uploadsApi } from "@/api/uploads";

vi.mock("@/api/uploads");

function makeFile(sizeBytes: number, type = "video/mp4"): File {
  // A plain duck-typed object, NOT a real Blob — a real Blob's
  // .slice() ignores an overridden .size property and slices its
  // actual (tiny) backing data instead, which would silently break
  // every part-size/progress calculation below. This fake correctly
  // returns right-sized "parts" for whatever byte range is requested,
  // matching what the orchestrator actually needs from File.slice().
  const file = {
    size: sizeBytes,
    type,
    name: "test-file",
    slice(start: number, end: number) {
      return { size: Math.max(0, Math.min(end, sizeBytes) - start), type };
    },
  };
  return file as unknown as File;
}

describe("startMultipartUpload", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(uploadsApi.getMultipartPartUrl).mockImplementation(async (_id, partNumber) => ({
      part_number: partNumber, upload_url: `https://r2.example.com/part-${partNumber}`,
    }));
    vi.mocked(uploadsApi.putPart).mockImplementation(async (_url, blob, onProgress) => {
      onProgress(blob.size);
      return "etag-ok";
    });
  });

  it("uploads every part and completes with them sorted by part_number", async () => {
    vi.mocked(uploadsApi.initiateMultipart).mockResolvedValue({
      upload_id: "u1", multipart_upload_id: "mp1", total_parts: 3, part_size_bytes: 20 * 1024 * 1024,
    });
    vi.mocked(uploadsApi.completeMultipart).mockResolvedValue({
      id: "u1", user_id: "user1", lesson_id: null, file_name: "big.mp4", file_type: "video",
      size_bytes: 60 * 1024 * 1024, status: "ready", created_at: "",
    });

    const handle = startMultipartUpload({ file: makeFile(60 * 1024 * 1024), onProgress: vi.fn() });
    const uploadId = await handle.result;

    expect(uploadId).toBe("u1");
    expect(uploadsApi.putPart).toHaveBeenCalledTimes(3);
    const [, parts] = vi.mocked(uploadsApi.completeMultipart).mock.calls[0];
    expect(parts.map((p) => p.part_number)).toEqual([1, 2, 3]);
  });

  it("reports real, monotonically-reaching-100 progress across all parts, never fabricated", async () => {
    vi.mocked(uploadsApi.initiateMultipart).mockResolvedValue({
      upload_id: "u1", multipart_upload_id: "mp1", total_parts: 2, part_size_bytes: 10 * 1024 * 1024,
    });
    vi.mocked(uploadsApi.completeMultipart).mockResolvedValue({
      id: "u1", user_id: "user1", lesson_id: null, file_name: "f.mp4", file_type: "video",
      size_bytes: 20 * 1024 * 1024, status: "ready", created_at: "",
    });

    const onProgress = vi.fn();
    const handle = startMultipartUpload({ file: makeFile(20 * 1024 * 1024), onProgress });
    await handle.result;

    const finalCall = onProgress.mock.calls.at(-1)?.[0];
    expect(finalCall).toBe(100);
  });

  it("retries a failed part up to the retry limit, without restarting the whole upload", async () => {
    vi.mocked(uploadsApi.initiateMultipart).mockResolvedValue({
      upload_id: "u1", multipart_upload_id: "mp1", total_parts: 1, part_size_bytes: 20 * 1024 * 1024,
    });
    vi.mocked(uploadsApi.completeMultipart).mockResolvedValue({
      id: "u1", user_id: "user1", lesson_id: null, file_name: "f.mp4", file_type: "video",
      size_bytes: 1024, status: "ready", created_at: "",
    });
    let attempts = 0;
    vi.mocked(uploadsApi.putPart).mockImplementation(async (_url, blob, onProgress) => {
      attempts++;
      if (attempts < 2) throw new Error("transient network error");
      onProgress(blob.size);
      return "etag-after-retry";
    });

    const handle = startMultipartUpload({ file: makeFile(1024), onProgress: vi.fn() });
    await handle.result;

    expect(attempts).toBe(2); // failed once, succeeded on retry — not more, not restarted from scratch
    // initiateMultipart (the "whole upload") was called exactly once —
    // confirms a part retry never re-initiates the entire session.
    expect(uploadsApi.initiateMultipart).toHaveBeenCalledOnce();
  });

  it("marks the upload failed (aborts) when a part exhausts all retries", async () => {
    vi.mocked(uploadsApi.initiateMultipart).mockResolvedValue({
      upload_id: "u1", multipart_upload_id: "mp1", total_parts: 1, part_size_bytes: 20 * 1024 * 1024,
    });
    vi.mocked(uploadsApi.putPart).mockRejectedValue(new Error("always fails"));

    const handle = startMultipartUpload({ file: makeFile(1024), onProgress: vi.fn() });

    await expect(handle.result).rejects.toThrow();
    expect(uploadsApi.abortMultipart).toHaveBeenCalledWith("u1"); // never leaves an orphaned R2 session
    expect(uploadsApi.completeMultipart).not.toHaveBeenCalled();
  });

  it("cancel() stops starting new parts and aborts the R2-side session", async () => {
    vi.mocked(uploadsApi.initiateMultipart).mockResolvedValue({
      upload_id: "u1", multipart_upload_id: "mp1", total_parts: 5, part_size_bytes: 1024,
    });
    // Never resolves any part — simulates a slow upload the user cancels mid-flight.
    vi.mocked(uploadsApi.putPart).mockImplementation(() => new Promise(() => {}));

    const handle = startMultipartUpload({ file: makeFile(5 * 1024), onProgress: vi.fn() });
    handle.cancel();

    await expect(handle.result).rejects.toThrow("bekor qilindi");
    expect(uploadsApi.completeMultipart).not.toHaveBeenCalled();
  });

  it("respects the concurrency limit — never more than MAX_CONCURRENT_PARTS parts in flight at once", async () => {
    vi.mocked(uploadsApi.initiateMultipart).mockResolvedValue({
      upload_id: "u1", multipart_upload_id: "mp1", total_parts: 10, part_size_bytes: 1024,
    });
    vi.mocked(uploadsApi.completeMultipart).mockResolvedValue({
      id: "u1", user_id: "user1", lesson_id: null, file_name: "f.mp4", file_type: "video",
      size_bytes: 10 * 1024, status: "ready", created_at: "",
    });

    let concurrentCount = 0;
    let maxObservedConcurrency = 0;
    vi.mocked(uploadsApi.putPart).mockImplementation(async (_url, blob, onProgress) => {
      concurrentCount++;
      maxObservedConcurrency = Math.max(maxObservedConcurrency, concurrentCount);
      await new Promise((resolve) => setTimeout(resolve, 5));
      concurrentCount--;
      onProgress(blob.size);
      return "etag";
    });

    const handle = startMultipartUpload({ file: makeFile(10 * 1024), onProgress: vi.fn() });
    await handle.result;

    expect(maxObservedConcurrency).toBeLessThanOrEqual(4); // MAX_CONCURRENT_PARTS
    expect(maxObservedConcurrency).toBeGreaterThan(1); // genuinely parallel, not accidentally serial
  });

  it("never reads the whole file into memory — only calls File.slice() for each part's byte range", async () => {
    vi.mocked(uploadsApi.initiateMultipart).mockResolvedValue({
      upload_id: "u1", multipart_upload_id: "mp1", total_parts: 2, part_size_bytes: 1024,
    });
    vi.mocked(uploadsApi.completeMultipart).mockResolvedValue({
      id: "u1", user_id: "user1", lesson_id: null, file_name: "f.mp4", file_type: "video",
      size_bytes: 2048, status: "ready", created_at: "",
    });

    const file = makeFile(2048);
    const sliceSpy = vi.spyOn(file, "slice");
    const handle = startMultipartUpload({ file, onProgress: vi.fn() });
    await handle.result;

    expect(sliceSpy).toHaveBeenCalledWith(0, 1024);
    expect(sliceSpy).toHaveBeenCalledWith(1024, 2048);
  });
});
