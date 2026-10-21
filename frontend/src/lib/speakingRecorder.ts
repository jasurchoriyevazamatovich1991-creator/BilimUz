/** Task 6 — browser-capability helpers for the Speaking recorder. */
export type RecorderState = "idle" | "requesting" | "recording" | "stopped" | "uploading" | "uploaded" | "error";

/** Longest single take; recording stops automatically after this. */
export const MAX_RECORDING_SECONDS = 15 * 60;

const PREFERRED_MIME_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/ogg", "audio/mp4"];

export function isRecordingSupported(): boolean {
  return (
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices &&
    typeof navigator.mediaDevices.getUserMedia === "function" &&
    typeof window !== "undefined" &&
    typeof window.MediaRecorder !== "undefined"
  );
}

export function pickMimeType(): string | undefined {
  const isSupported = window.MediaRecorder?.isTypeSupported;
  if (typeof isSupported !== "function") return undefined;
  return PREFERRED_MIME_TYPES.find((t) => window.MediaRecorder.isTypeSupported(t));
}

export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}
