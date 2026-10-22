/**
 * Task 6 — IELTS Speaking response recorder (MediaRecorder API).
 *
 * States: idle → requesting (mic permission prompt) → recording →
 * stopped (local playback, re-record or upload) → uploading → uploaded,
 * or error at any step. "Uploaded" is shown only after the server
 * confirmed the upload (201); nothing is claimed earlier.
 *
 * The recording leaves the browser only through the authenticated
 * POST /attempts/{id}/questions/{qid}/audio endpoint, which re-checks
 * ownership, attempt status, question eligibility, type and size. A
 * previously saved recording is played back through the authenticated
 * stream endpoint as a Blob — no public or signed URL is ever used.
 */
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/api/client";
import { SPEAKING_AUDIO_MAX_BYTES, attemptsApi } from "@/api/attempts";
import { MAX_RECORDING_SECONDS, formatDuration, isRecordingSupported, pickMimeType, type RecorderState } from "@/lib/speakingRecorder";

function permissionMessage(err: unknown): string {
  const name = (err as { name?: string } | null)?.name;
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "Mikrofonga ruxsat berilmadi. Brauzer sozlamalarida ushbu sayt uchun mikrofonga ruxsat bering va qayta urinib ko'ring.";
  }
  if (name === "NotFoundError" || name === "OverconstrainedError") return "Mikrofon topilmadi. Mikrofonni ulang va qayta urinib ko'ring.";
  if (name === "NotReadableError") return "Mikrofon boshqa dastur tomonidan band. Uni yoping va qayta urinib ko'ring.";
  return "Mikrofonni ishga tushirib bo'lmadi.";
}

function uploadMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 413) return "Yozuv juda katta (maksimal 20 MB). Qisqaroq yozib ko'ring.";
    if (err.status === 409) return "Urinish faol emas — yozuvni yuborib bo'lmaydi.";
    if (err.status === 401 || err.status === 403 || err.status === 404) return "Yozuvni yuborishga ruxsat yo'q.";
    if (err.status === 422) return err.message || "Yozuv qabul qilinmadi.";
    // Task 10.1 — the server could not verify the recording (ffprobe unavailable).
    if (err.status === 503) return err.message || "Server yozuvni hozir tekshira olmadi. Birozdan keyin qayta yuboring.";
    if (err.status === undefined) return "Tarmoq xatosi — yozuv yuborilmadi. Internet aloqasini tekshirib, qayta yuboring.";
  }
  return "Yozuvni yuborib bo'lmadi. Qayta urinib ko'ring.";
}

interface SpeakingRecorderProps {
  attemptId: string;
  questionId: string;
  /** A recording is already stored on the server for this question. */
  hasSavedAudio: boolean;
  /** Called only after the server confirmed the upload. */
  onUploaded: (questionId: string) => void;
}

export function SpeakingRecorder({ attemptId, questionId, hasSavedAudio, onUploaded }: SpeakingRecorderProps) {
  const supported = isRecordingSupported();
  const [state, setState] = useState<RecorderState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [progress, setProgress] = useState(0);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [localUrl, setLocalUrl] = useState<string | null>(null);
  const [savedUrl, setSavedUrl] = useState<string | null>(null);
  const [savedLoading, setSavedLoading] = useState(false);
  const [saved, setSaved] = useState(hasSavedAudio);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef(0);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);
  const urlsRef = useRef<string[]>([]);

  function stopTracks() {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }

  function clearTick() {
    if (tickRef.current) clearInterval(tickRef.current);
    tickRef.current = null;
  }

  function trackUrl(b: Blob): string {
    const url = URL.createObjectURL(b);
    urlsRef.current.push(url);
    return url;
  }

  useEffect(() => {
    mountedRef.current = true;
    const urls = urlsRef.current; // the same array object for the component's lifetime
    return () => {
      // Leaving the question: stop the mic and timers. An upload already in
      // flight is allowed to finish (its success still updates the attempt
      // cache through onUploaded) rather than being silently dropped.
      mountedRef.current = false;
      clearTick();
      const rec = recorderRef.current;
      if (rec && rec.state !== "inactive") {
        rec.onstop = null;
        rec.stop();
      }
      stopTracks();
      urls.forEach((u) => URL.revokeObjectURL(u));
    };
  }, []);

  // Warn before closing/reloading the tab while a take would be lost.
  const unsaved = state === "recording" || state === "stopped" || state === "uploading" || (state === "error" && blob !== null);
  useEffect(() => {
    if (!unsaved) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [unsaved]);

  async function startRecording() {
    setError(null);
    setBlob(null);
    setLocalUrl(null);
    setProgress(0);
    setState("requesting");
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      if (!mountedRef.current) return;
      setError(permissionMessage(err));
      setState("error");
      return;
    }
    if (!mountedRef.current) {
      stream.getTracks().forEach((t) => t.stop());
      return;
    }
    streamRef.current = stream;
    let recorder: MediaRecorder;
    try {
      const mimeType = pickMimeType();
      recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
    } catch {
      stopTracks();
      setError("Brauzer audio yozishni qo'llab-quvvatlamaydi.");
      setState("error");
      return;
    }
    chunksRef.current = [];
    recorder.ondataavailable = (e: BlobEvent) => {
      if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
    };
    recorder.onerror = () => {
      clearTick();
      stopTracks();
      if (!mountedRef.current) return;
      setError("Yozish vaqtida xatolik yuz berdi. Qayta yozib ko'ring.");
      setState("error");
    };
    recorder.onstop = () => {
      clearTick();
      stopTracks();
      if (!mountedRef.current) return;
      const type = recorder.mimeType || chunksRef.current[0]?.type || "audio/webm";
      const result = new Blob(chunksRef.current, { type: type.split(";")[0] });
      if (result.size === 0) {
        setError("Yozuv bo'sh chiqdi. Qayta yozib ko'ring.");
        setState("error");
        return;
      }
      setBlob(result);
      setLocalUrl(trackUrl(result));
      if (result.size > SPEAKING_AUDIO_MAX_BYTES) {
        setError("Yozuv juda katta (maksimal 20 MB). Qisqaroq yozib ko'ring.");
        setState("error");
        return;
      }
      setState("stopped");
    };
    recorderRef.current = recorder;
    recorder.start(1000);
    startedAtRef.current = Date.now();
    setElapsed(0);
    setState("recording");
    tickRef.current = setInterval(() => {
      const secs = (Date.now() - startedAtRef.current) / 1000;
      setElapsed(secs);
      if (secs >= MAX_RECORDING_SECONDS) stopRecording();
    }, 250);
  }

  function stopRecording() {
    const rec = recorderRef.current;
    if (rec && rec.state !== "inactive") rec.stop();
  }

  async function upload() {
    if (!blob) return;
    if (blob.size > SPEAKING_AUDIO_MAX_BYTES) {
      setError("Yozuv juda katta (maksimal 20 MB). Qisqaroq yozib ko'ring.");
      setState("error");
      return;
    }
    const controller = new AbortController();
    abortRef.current = controller;
    setError(null);
    setProgress(0);
    setState("uploading");
    try {
      await attemptsApi.uploadSpeakingAudio(attemptId, questionId, blob, {
        signal: controller.signal,
        onProgress: (f) => mountedRef.current && setProgress(f),
      });
      onUploaded(questionId);
      if (!mountedRef.current) return;
      setSaved(true);
      setSavedUrl(null); // the server copy changed; re-fetch on demand
      setState("uploaded");
    } catch (err) {
      if (!mountedRef.current) return;
      if (controller.signal.aborted) {
        setError("Yuborish bekor qilindi. Yozuv saqlanmadi.");
      } else {
        setError(uploadMessage(err));
      }
      setState("error");
    } finally {
      abortRef.current = null;
    }
  }

  function cancelUpload() {
    abortRef.current?.abort();
  }

  async function loadSaved() {
    setSavedLoading(true);
    try {
      const data = await attemptsApi.getOwnSpeakingAudio(attemptId, questionId);
      if (mountedRef.current) setSavedUrl(trackUrl(data));
    } catch {
      if (mountedRef.current) setError("Saqlangan yozuvni yuklab bo'lmadi.");
    } finally {
      if (mountedRef.current) setSavedLoading(false);
    }
  }

  if (!supported) {
    return (
      <div className="rounded-md border border-border p-4" data-testid="speaking-recorder">
        <p role="alert" className="text-sm text-destructive">
          Brauzeringiz audio yozishni qo'llab-quvvatlamaydi. Chrome, Edge, Firefox yoki Safari'ning so'nggi versiyasidan foydalaning.
        </p>
      </div>
    );
  }

  const busy = state === "requesting" || state === "uploading";

  return (
    <div className="space-y-3 rounded-md border border-border p-4" data-testid="speaking-recorder" data-state={state}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-medium text-foreground">Og'zaki javob (audio)</span>
        <span className="font-mono text-sm text-foreground/70" data-testid="recording-duration" aria-label="Yozuv davomiyligi">
          {state === "recording" ? <span className="mr-1 text-destructive" aria-hidden="true">●</span> : null}
          {formatDuration(elapsed)}
        </span>
      </div>

      <p className="text-xs text-foreground/60" aria-live="polite" data-testid="recorder-status">
        {state === "idle" && (saved ? "Javob yozuvi saqlangan. Xohlasangiz qayta yozishingiz mumkin." : "Yozishni boshlaganingizda brauzer mikrofon ruxsatini so'raydi.")}
        {state === "requesting" && "Mikrofon ruxsati so'ralmoqda..."}
        {state === "recording" && "Yozilmoqda..."}
        {state === "stopped" && "Yozuv tayyor — tinglab ko'ring va yuboring. Hali yuborilmagan."}
        {state === "uploading" && `Yuborilmoqda... ${Math.round(progress * 100)}%`}
        {state === "uploaded" && "Yozuv saqlandi."}
        {state === "error" && "Xatolik"}
      </p>

      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}

      {localUrl && (state === "stopped" || state === "error" || state === "uploading" || state === "uploaded") ? (
        <audio controls src={localUrl} aria-label="Yozilgan javobni tinglash" className="w-full" data-testid="local-playback" />
      ) : null}

      {saved && !localUrl && state !== "recording" && state !== "requesting" ? (
        savedUrl ? (
          <audio controls src={savedUrl} aria-label="Saqlangan javob" className="w-full" data-testid="saved-playback" />
        ) : (
          <Button type="button" variant="outline" size="sm" onClick={loadSaved} disabled={savedLoading}>
            {savedLoading ? "Yuklanmoqda..." : "Saqlangan yozuvni tinglash"}
          </Button>
        )
      ) : null}

      <div className="flex flex-wrap gap-2">
        {state === "recording" ? (
          <Button type="button" variant="destructive" onClick={stopRecording}>To'xtatish</Button>
        ) : state === "uploading" ? (
          <Button type="button" variant="outline" onClick={cancelUpload}>Bekor qilish</Button>
        ) : (
          <>
            <Button type="button" variant={blob || saved ? "outline" : "default"} onClick={startRecording} disabled={busy}>
              {blob || saved ? "Qayta yozish" : "Yozishni boshlash"}
            </Button>
            {blob && (state === "stopped" || (state === "error" && blob.size <= SPEAKING_AUDIO_MAX_BYTES)) ? (
              <Button type="button" onClick={upload}>{state === "error" ? "Qayta yuborish" : "Yozuvni yuborish"}</Button>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
