/**
 * New file — Sprint 27. `useUploadFile` composes the full presigned
 * flow into one call the UI invokes once: create session -> real XHR
 * PUT to R2 (with live progress) -> finalize. Each stage's real
 * failure mode is distinguishable (see UploadStage below) so the UI
 * can show an accurate error instead of a generic one.
 *
 * Sprint 27 Amendment: `useUploadFile` now automatically routes to
 * either this original single-PUT flow (files at or below
 * MULTIPART_THRESHOLD_BYTES — completely unchanged) or the new
 * multipart orchestration (lib/multipartUpload.ts) for larger files —
 * the caller never chooses, matching the explicit "user should NOT
 * need to manually choose multipart mode" requirement.
 */
import { useRef } from "react";
import { useMutation, useQuery, useQueryClient, type UseMutationResult } from "@tanstack/react-query";
import { uploadsApi, type UploadOut } from "@/api/uploads";
import { useToastStore } from "@/store/toastStore";
import { ApiError } from "@/api/client";
import { MULTIPART_THRESHOLD_BYTES } from "@/constants/uploads";
import { startMultipartUpload, type MultipartUploadHandle } from "@/lib/multipartUpload";

export type UploadStage = "idle" | "creating-session" | "uploading" | "finalizing" | "done" | "error";

export function useMyUploads(params: { page: number; per_page: number }) {
  return useQuery({ queryKey: ["uploads", "list", params], queryFn: () => uploadsApi.listMine(params) });
}

export function useDeleteUpload() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (uploadId: string) => uploadsApi.remove(uploadId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["uploads", "list"] });
      addToast("Fayl o'chirildi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "O'chirib bo'lmadi"),
  });
}

export function useSignedViewUrl() {
  return useMutation({
    mutationFn: (uploadId: string) => uploadsApi.getViewUrl(uploadId),
  });
}

interface UploadFileArgs {
  file: File;
  lessonId?: string;
  onProgress?: (percent: number) => void;
}

/**
 * The single composed mutation the FileUploader component calls.
 * Real, verified backend contract at every stage — no fake progress
 * (0-100% comes directly from the browser's real XHR upload.progress
 * events).
 *
 * Sprint 27 Amendment: returns `cancelUpload()` alongside the mutation
 * object — calls the in-flight multipart handle's `cancel()` if one
 * exists (no-op otherwise, e.g. during the small-file single-PUT path,
 * which completes quickly and has no separate cancellable session on
 * the backend to abort).
 */
export function useUploadFile(): UseMutationResult<UploadOut, Error, UploadFileArgs> & { cancelUpload: () => void } {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);
  const currentHandleRef = useRef<MultipartUploadHandle | null>(null);

  const mutation = useMutation({
    mutationFn: async ({ file, lessonId, onProgress }: UploadFileArgs) => {
      currentHandleRef.current = null;

      if (file.size <= MULTIPART_THRESHOLD_BYTES) {
        // Small file — the original, completely unchanged Sprint 27 flow.
        const presigned = await uploadsApi.createPresignedUpload({
          original_filename: file.name,
          content_type: file.type,
          size_bytes: file.size,
          lesson_id: lessonId,
        });
        await uploadsApi.putToPresignedUrl(presigned, file, (percent) => onProgress?.(percent));
        return uploadsApi.finalize(presigned.upload_id);
      }

      // Large file — the new multipart orchestration.
      const handle = startMultipartUpload({ file, lessonId, onProgress: (percent) => onProgress?.(percent) });
      currentHandleRef.current = handle;
      const uploadId = await handle.result;
      currentHandleRef.current = null;
      return uploadsApi.get(uploadId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["uploads", "list"] });
      addToast("Fayl muvaffaqiyatli yuklandi", "success");
    },
    onError: (error) => {
      currentHandleRef.current = null;
      addToast(error.message || "Yuklab bo'lmadi");
    },
  });

  return {
    ...mutation,
    cancelUpload: () => currentHandleRef.current?.cancel(),
  };
}
