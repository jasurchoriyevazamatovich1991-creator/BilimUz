/**
 * Reusable component — Sprint 27, extended by the Sprint 27 Amendment.
 * Drag & drop + click-to-browse, real progress (from the browser's own
 * XHR upload events, never fabricated).
 *
 * Sprint 27 Amendment: automatically routes large files (> 100 MB,
 * MULTIPART_THRESHOLD_BYTES) through R2 Multipart Upload
 * (lib/multipartUpload.ts) instead of a single PUT — the user never
 * chooses; `useUploadFile` (hooks/useUploads.ts) makes that decision
 * internally. Videos up to 2 GB (MAX_SIZE_VIDEO_BYTES) are accepted;
 * this is a CLIENT-SIDE UX check only — the backend re-validates size
 * independently and is the real enforcement point.
 *
 * "Bekor qilish" now has two meanings depending on when it's clicked:
 * before upload starts, it just clears the staged file (as before);
 * during an in-progress multipart upload, it calls the real
 * `cancelUpload()` (stops starting new parts, aborts the R2-side
 * session — in-flight parts are allowed to finish rather than being
 * forcibly interrupted, a documented, deliberate scope boundary, see
 * docs/Sprint27_R2_Media_Storage.md).
 */
import { useRef, useState, type DragEvent } from "react";
import { Button } from "@/components/ui/button";
import { useUploadFile } from "@/hooks/useUploads";
import { MAX_SIZE_VIDEO_BYTES } from "@/constants/uploads";

const ACCEPTED_TYPES = {
  video: ["video/mp4", "video/webm"],
  audio: ["audio/mpeg", "audio/wav", "audio/ogg", "audio/mp4"],
  pdf: ["application/pdf"],
  image: ["image/jpeg", "image/png", "image/webp", "image/gif"],
};

const ALL_ACCEPTED = Object.values(ACCEPTED_TYPES).flat();

type Stage = "idle" | "preparing" | "uploading" | "finalizing" | "failed" | "cancelled";

const STAGE_LABEL: Record<Stage, string> = {
  idle: "",
  preparing: "Tayyorlanmoqda...",
  uploading: "Yuklanmoqda...",
  finalizing: "Yakunlanmoqda...",
  failed: "Yuklab bo'lmadi",
  cancelled: "Bekor qilindi",
};

interface FileUploaderProps {
  lessonId?: string;
  onSuccess?: (uploadId: string) => void;
  disabled?: boolean;
}

export function FileUploader({ lessonId, onSuccess, disabled }: FileUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState<Stage>("idle");
  const [localError, setLocalError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const wasCancelledRef = useRef(false);
  const upload = useUploadFile();

  function validateAndSetFile(file: File) {
    setLocalError(null);
    setStage("idle");
    if (!ALL_ACCEPTED.includes(file.type)) {
      setLocalError(`Qo'llab-quvvatlanmaydigan fayl turi: ${file.type || "noma'lum"}`);
      return;
    }
    if (file.type.startsWith("video/") && file.size > MAX_SIZE_VIDEO_BYTES) {
      // Client-side UX check only — the backend independently
      // re-validates size and is the real enforcement point.
      setLocalError(`Video juda katta — maksimal ${(MAX_SIZE_VIDEO_BYTES / (1024 * 1024 * 1024)).toFixed(0)} GB`);
      return;
    }
    setSelectedFile(file);
    setProgress(0);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) validateAndSetFile(file);
  }

  function handleStartUpload() {
    if (!selectedFile) return;
    setStage("preparing");
    wasCancelledRef.current = false;

    upload.mutate(
      {
        file: selectedFile,
        lessonId,
        onProgress: (percent) => {
          setProgress(percent);
          setStage(percent >= 100 ? "finalizing" : "uploading");
        },
      },
      {
        onSuccess: (result) => {
          setSelectedFile(null);
          setProgress(0);
          setStage("idle");
          onSuccess?.(result.id);
        },
        onError: () => {
          setStage(wasCancelledRef.current ? "cancelled" : "failed");
        },
      },
    );
  }

  function handleCancelDuringUpload() {
    wasCancelledRef.current = true;
    upload.cancelUpload();
  }

  const isUploading = upload.isPending;

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        className={`cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
          isDragging ? "border-primary bg-primary/5" : "border-border"
        } ${disabled ? "cursor-not-allowed opacity-50" : "hover:border-primary/40"}`}
      >
        <p className="text-2xl">📤</p>
        <p className="mt-2 text-sm font-medium text-foreground">Faylni shu yerga tashlang yoki tanlang</p>
        <p className="mt-1 text-xs text-foreground/50">Video (2 GB gacha) / Audio / PDF / Image</p>
        <input
          ref={inputRef}
          type="file"
          accept={ALL_ACCEPTED.join(",")}
          className="hidden"
          disabled={disabled}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) validateAndSetFile(file);
          }}
        />
      </div>

      {localError ? <p className="mt-2 text-sm text-destructive">{localError}</p> : null}

      {selectedFile ? (
        <div className="mt-4 rounded-md border border-border p-3">
          <div className="flex items-center justify-between text-sm">
            <span className="truncate text-foreground">{selectedFile.name}</span>
            <span className="text-foreground/50">{(selectedFile.size / (1024 * 1024)).toFixed(1)} MB</span>
          </div>

          {isUploading ? (
            <div className="mt-2">
              <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${progress}%` }} />
              </div>
              <div className="mt-1 flex items-center justify-between">
                <p className="text-xs text-foreground/50">
                  {stage === "uploading" ? `${STAGE_LABEL[stage]} ${progress}%` : STAGE_LABEL[stage]}
                </p>
                <button type="button" onClick={handleCancelDuringUpload} className="text-xs text-destructive hover:underline">
                  Bekor qilish
                </button>
              </div>
            </div>
          ) : (
            <div className="mt-3">
              {stage === "failed" || stage === "cancelled" ? (
                <p className={`mb-2 text-xs ${stage === "failed" ? "text-destructive" : "text-foreground/50"}`}>
                  {STAGE_LABEL[stage]}
                </p>
              ) : null}
              <div className="flex gap-2">
                <Button type="button" size="sm" onClick={handleStartUpload}>
                  {stage === "failed" ? "Qayta urinish" : "Yuklash"}
                </Button>
                <Button type="button" size="sm" variant="outline" onClick={() => setSelectedFile(null)}>
                  Bekor qilish
                </Button>
              </div>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
