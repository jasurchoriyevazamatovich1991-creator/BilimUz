/**
 * New file — Sprint 27 R2 Media Storage. Every shape verified directly
 * against real backend app/modules/uploads/{schemas,router}.py before
 * writing. The presigned flow's actual R2 PUT is done via a raw
 * fetch()/XMLHttpRequest directly to `upload_url` (NOT through
 * httpClient — that URL is R2, not this backend, and must never carry
 * this app's Authorization header), while every other call here goes
 * through the normal authenticated httpClient exactly like every other
 * api/*.ts file.
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface UploadOut {
  id: string;
  user_id: string | null;
  lesson_id: string | null;
  file_name: string;
  file_type: string;
  size_bytes: number | null;
  status: string;
  created_at: string;
}

export interface CreatePresignedUploadRequest {
  original_filename: string;
  content_type: string;
  size_bytes: number;
  lesson_id?: string;
}

export interface PresignedUploadOut {
  upload_id: string;
  upload_url: string;
  required_headers: Record<string, string>;
}

export interface ViewUrlOut {
  view_url: string;
}

// --- Sprint 27 Amendment: R2 Multipart Upload (2 GB video support) ---

export interface InitiateMultipartUploadRequest {
  original_filename: string;
  content_type: string;
  size_bytes: number;
  lesson_id?: string;
}

export interface InitiateMultipartUploadOut {
  upload_id: string;
  multipart_upload_id: string;
  total_parts: number;
  part_size_bytes: number;
}

export interface PartUrlOut {
  part_number: number;
  upload_url: string;
}

export interface CompletedPart {
  part_number: number;
  etag: string;
}

export const uploadsApi = {
  createPresignedUpload: (data: CreatePresignedUploadRequest) =>
    unwrap<PresignedUploadOut>(httpClient.post("/uploads/presigned", data)),

  finalize: (uploadId: string) => unwrap<UploadOut>(httpClient.patch(`/uploads/${uploadId}/finalize`)),

  getViewUrl: (uploadId: string) => unwrap<ViewUrlOut>(httpClient.get(`/uploads/${uploadId}/view-url`)),

  listMine: (params: { page: number; per_page: number }) =>
    unwrap<PaginatedResponse<UploadOut>>(httpClient.get("/uploads/me", { params })),

  get: (uploadId: string) => unwrap<UploadOut>(httpClient.get(`/uploads/${uploadId}`)),

  remove: (uploadId: string) => httpClient.delete(`/uploads/${uploadId}`),

  /**
   * The actual browser -> R2 direct PUT. Deliberately raw XMLHttpRequest
   * (not fetch/axios) — XHR is the only web-standard way to get real
   * upload progress events, which fetch's streaming body API does not
   * expose for uploads. Resolves when the PUT succeeds, rejects with
   * the XHR status on failure. Never touches this backend's httpClient
   * — this request goes straight to R2's presigned URL, and must NOT
   * carry this app's JWT Authorization header (R2 would reject an
   * unexpected header on a presigned request, and the app's own
   * credentials have no business being sent to a third-party host).
   */
  putToPresignedUrl: (
    presigned: PresignedUploadOut,
    file: File,
    onProgress: (percent: number) => void,
  ): Promise<void> => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", presigned.upload_url);
      Object.entries(presigned.required_headers).forEach(([key, value]) => xhr.setRequestHeader(key, value));

      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
      });
      xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) resolve();
        else reject(new Error(`Yuklash muvaffaqiyatsiz (${xhr.status})`));
      });
      xhr.addEventListener("error", () => reject(new Error("Tarmoq xatosi")));
      xhr.addEventListener("abort", () => reject(new Error("Yuklash bekor qilindi")));

      xhr.send(file);
    });
  },

  // --- Sprint 27 Amendment: R2 Multipart Upload ---

  initiateMultipart: (data: InitiateMultipartUploadRequest) =>
    unwrap<InitiateMultipartUploadOut>(httpClient.post("/uploads/multipart/initiate", data)),

  getMultipartPartUrl: (uploadId: string, partNumber: number) =>
    unwrap<PartUrlOut>(httpClient.post(`/uploads/multipart/${uploadId}/part-url`, { part_number: partNumber })),

  completeMultipart: (uploadId: string, parts: CompletedPart[]) =>
    unwrap<UploadOut>(httpClient.post(`/uploads/multipart/${uploadId}/complete`, { parts })),

  abortMultipart: (uploadId: string) => httpClient.post(`/uploads/multipart/${uploadId}/abort`),

  /**
   * Uploads exactly ONE part directly to R2 via its presigned URL.
   * Resolves with the part's ETag (read from the response header) —
   * R2/S3 requires this exact ETag be reported back in the
   * CompleteMultipartUpload call for each part, matched by part
   * number. Same XHR-for-real-progress reasoning as putToPresignedUrl.
   */
  putPart: (uploadUrl: string, blob: Blob, onProgress: (loadedBytes: number) => void): Promise<string> => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", uploadUrl);

      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) onProgress(e.loaded);
      });
      xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          const etag = xhr.getResponseHeader("ETag");
          if (!etag) {
            reject(new Error("R2 ETag qaytarmadi"));
            return;
          }
          resolve(etag);
        } else {
          reject(new Error(`Qism yuklanmadi (${xhr.status})`));
        }
      });
      xhr.addEventListener("error", () => reject(new Error("Tarmoq xatosi")));
      xhr.addEventListener("abort", () => reject(new Error("Yuklash bekor qilindi")));

      xhr.send(blob);
    });
  },
};
