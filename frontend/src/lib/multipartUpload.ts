/**
 * Sprint 27 Amendment — R2 Multipart Upload orchestration. Pure logic,
 * separated from the React Query hook wrapper (hooks/useUploads.ts) so
 * it's directly unit-testable without rendering anything.
 *
 * Design:
 * - File.slice() creates each part's Blob — the full 2 GB file is
 *   NEVER read into memory at once, only one part's worth (<=20MB) per
 *   concurrent slot.
 * - A small concurrency pool (MAX_CONCURRENT_PARTS) uploads several
 *   parts in parallel without unbounded concurrent requests.
 * - Each part is retried independently (MULTIPART_PART_RETRY_LIMIT,
 *   simple linear backoff) — a single failed part never restarts the
 *   whole multi-gigabyte upload.
 * - Progress is the real sum of bytes actually PUT so far across every
 *   part (from each part's own XHR progress events), divided by the
 *   real file size — never a fabricated animation.
 * - Cancellation stops STARTING new parts and lets any already-in-flight
 *   part finish (a genuine mid-XHR abort would need exposing the raw
 *   XHR instance per part, not implemented this sprint — documented as
 *   a known limitation), then aborts the whole R2-side session so
 *   nothing is left orphaned.
 */
import { uploadsApi, type CompletedPart } from "@/api/uploads";
import { MAX_CONCURRENT_PARTS, MULTIPART_PART_RETRY_LIMIT, MULTIPART_PART_SIZE_BYTES } from "@/constants/uploads";

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Runs `worker` over every item in `items`, at most `limit` at a time. */
async function runWithConcurrencyLimit<T>(items: T[], limit: number, worker: (item: T) => Promise<void>): Promise<void> {
  let cursor = 0;
  async function runNext(): Promise<void> {
    const index = cursor++;
    if (index >= items.length) return;
    await worker(items[index]);
    await runNext();
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, () => runNext()));
}

export interface MultipartUploadArgs {
  file: File;
  lessonId?: string;
  onProgress: (percent: number) => void;
}

export interface MultipartUploadHandle {
  /** Resolves with the finalized upload's id once R2's
   * CompleteMultipartUpload succeeds. */
  result: Promise<string>;
  /** Stops starting new parts and aborts the R2-side session. */
  cancel: () => void;
}

export function startMultipartUpload({ file, lessonId, onProgress }: MultipartUploadArgs): MultipartUploadHandle {
  let cancelled = false;
  let uploadId: string | null = null;

  const result = (async (): Promise<string> => {
    const initiated = await uploadsApi.initiateMultipart({
      original_filename: file.name,
      content_type: file.type,
      size_bytes: file.size,
      lesson_id: lessonId,
    });
    uploadId = initiated.upload_id;

    if (cancelled) {
      await uploadsApi.abortMultipart(uploadId);
      throw new Error("Yuklash bekor qilindi");
    }

    const totalParts = initiated.total_parts;
    const partSize = initiated.part_size_bytes || MULTIPART_PART_SIZE_BYTES;
    const partBytesUploaded = new Array<number>(totalParts).fill(0);

    function reportProgress() {
      const uploaded = partBytesUploaded.reduce((sum, n) => sum + n, 0);
      onProgress(Math.round((uploaded / file.size) * 100));
    }

    const completedParts: CompletedPart[] = [];

    async function uploadOnePart(partNumber: number): Promise<void> {
      if (cancelled) return;
      const start = (partNumber - 1) * partSize;
      const end = Math.min(start + partSize, file.size);
      const blob = file.slice(start, end);

      let lastError: Error | null = null;
      for (let attempt = 1; attempt <= MULTIPART_PART_RETRY_LIMIT; attempt++) {
        if (cancelled) return;
        try {
          const { upload_url } = await uploadsApi.getMultipartPartUrl(uploadId!, partNumber);
          const etag = await uploadsApi.putPart(upload_url, blob, (loadedBytes) => {
            partBytesUploaded[partNumber - 1] = loadedBytes;
            reportProgress();
          });
          completedParts.push({ part_number: partNumber, etag });
          partBytesUploaded[partNumber - 1] = blob.size;
          reportProgress();
          return;
        } catch (err) {
          lastError = err instanceof Error ? err : new Error(String(err));
          partBytesUploaded[partNumber - 1] = 0; // this attempt's progress doesn't count until it actually succeeds
          reportProgress();
          if (attempt < MULTIPART_PART_RETRY_LIMIT) await sleep(attempt * 500); // linear backoff
        }
      }
      throw lastError ?? new Error(`Qism ${partNumber} yuklanmadi`);
    }

    const partNumbers = Array.from({ length: totalParts }, (_, i) => i + 1);
    try {
      await runWithConcurrencyLimit(partNumbers, MAX_CONCURRENT_PARTS, uploadOnePart);
    } catch (err) {
      await uploadsApi.abortMultipart(uploadId).catch(() => {}); // never leave an orphaned R2 session, even on a real failure
      throw err;
    }

    if (cancelled) {
      await uploadsApi.abortMultipart(uploadId);
      throw new Error("Yuklash bekor qilindi");
    }

    completedParts.sort((a, b) => a.part_number - b.part_number);
    const finalUpload = await uploadsApi.completeMultipart(uploadId, completedParts);
    return finalUpload.id;
  })();

  return {
    result,
    cancel: () => {
      cancelled = true;
    },
  };
}
