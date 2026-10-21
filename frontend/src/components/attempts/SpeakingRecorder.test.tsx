/**
 * Task 6 — Speaking recorder state machine with a fake MediaRecorder and
 * getUserMedia (jsdom has neither). The upload API is mocked; the
 * backend's own validation is covered by the integration tests.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { SpeakingRecorder } from "./SpeakingRecorder";
import { formatDuration } from "@/lib/speakingRecorder";
import { attemptsApi } from "@/api/attempts";
import { ApiError } from "@/api/client";

vi.mock("@/api/attempts", async (orig) => {
  const actual = await orig<typeof import("@/api/attempts")>();
  return { ...actual, attemptsApi: { ...actual.attemptsApi, uploadSpeakingAudio: vi.fn(), getOwnSpeakingAudio: vi.fn() } };
});

class FakeRecorder {
  static instances: FakeRecorder[] = [];
  static isTypeSupported = (t: string) => t === "audio/webm;codecs=opus";
  static payloadSize = 64;
  state: "inactive" | "recording" = "inactive";
  mimeType: string;
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public stream: MediaStream, opts?: { mimeType?: string }) {
    this.mimeType = opts?.mimeType ?? "audio/webm";
    FakeRecorder.instances.push(this);
  }
  start() { this.state = "recording"; }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob([new Uint8Array(FakeRecorder.payloadSize)], { type: this.mimeType }) });
    this.onstop?.();
  }
}

const trackStop = vi.fn();
const getUserMedia = vi.fn();

function setup(props: Partial<Parameters<typeof SpeakingRecorder>[0]> = {}) {
  const onUploaded = vi.fn();
  render(<SpeakingRecorder attemptId="a1" questionId="q1" hasSavedAudio={false} onUploaded={onUploaded} {...props} />);
  return { onUploaded };
}

const status = () => screen.getByTestId("recorder-status");
const root = () => screen.getByTestId("speaking-recorder");

async function recordOnce() {
  fireEvent.click(screen.getByRole("button", { name: "Yozishni boshlash" }));
  await waitFor(() => expect(root()).toHaveAttribute("data-state", "recording"));
  fireEvent.click(screen.getByRole("button", { name: "To'xtatish" }));
  await waitFor(() => expect(root()).toHaveAttribute("data-state", "stopped"));
}

describe("SpeakingRecorder", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    FakeRecorder.instances = [];
    FakeRecorder.payloadSize = 64;
    getUserMedia.mockResolvedValue({ getTracks: () => [{ stop: trackStop }] });
    Object.defineProperty(navigator, "mediaDevices", { value: { getUserMedia }, configurable: true });
    Object.defineProperty(window, "MediaRecorder", { value: FakeRecorder, configurable: true, writable: true });
    let n = 0;
    Object.assign(URL, { createObjectURL: vi.fn(() => `blob:local-${++n}`), revokeObjectURL: vi.fn() });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("formats durations", () => {
    expect(formatDuration(0)).toBe("00:00");
    expect(formatDuration(75.9)).toBe("01:15");
  });

  it("explains when the browser cannot record", () => {
    Object.defineProperty(window, "MediaRecorder", { value: undefined, configurable: true, writable: true });
    setup();
    expect(screen.getByRole("alert")).toHaveTextContent("qo'llab-quvvatlamaydi");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("handles a denied microphone permission", async () => {
    getUserMedia.mockRejectedValue(Object.assign(new Error("denied"), { name: "NotAllowedError" }));
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Yozishni boshlash" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Mikrofonga ruxsat berilmadi");
    expect(root()).toHaveAttribute("data-state", "error");
    expect(screen.queryByRole("button", { name: /yuborish/i })).not.toBeInTheDocument();
    expect(attemptsApi.uploadSpeakingAudio).not.toHaveBeenCalled();
  });

  it("goes through requesting → recording → stopped with a timer and local playback, then uploads", async () => {
    let resolveMic!: (s: unknown) => void;
    getUserMedia.mockReturnValue(new Promise((r) => { resolveMic = r; }));
    vi.mocked(attemptsApi.uploadSpeakingAudio).mockImplementation(async (_a, _q, _b, opts) => {
      opts?.onProgress?.(0.5);
      return { question_id: "q1", mime_type: "audio/webm", size_bytes: 64 };
    });
    const { onUploaded } = setup();
    fireEvent.click(screen.getByRole("button", { name: "Yozishni boshlash" }));
    expect(root()).toHaveAttribute("data-state", "requesting");
    expect(status()).toHaveTextContent("ruxsati so'ralmoqda");
    expect(getUserMedia).toHaveBeenCalledWith({ audio: true });

    vi.useFakeTimers({ shouldAdvanceTime: true });
    await act(async () => resolveMic({ getTracks: () => [{ stop: trackStop }] }));
    expect(root()).toHaveAttribute("data-state", "recording");
    expect(FakeRecorder.instances[0].mimeType).toBe("audio/webm;codecs=opus");
    await act(async () => { vi.advanceTimersByTime(3200); });
    expect(screen.getByTestId("recording-duration")).toHaveTextContent("00:03");

    fireEvent.click(screen.getByRole("button", { name: "To'xtatish" }));
    expect(root()).toHaveAttribute("data-state", "stopped");
    expect(trackStop).toHaveBeenCalled();
    expect(screen.getByTestId("local-playback")).toHaveAttribute("src", "blob:local-1");
    expect(status()).toHaveTextContent("Hali yuborilmagan");
    expect(onUploaded).not.toHaveBeenCalled();
    vi.useRealTimers();

    fireEvent.click(screen.getByRole("button", { name: "Yozuvni yuborish" }));
    await waitFor(() => expect(root()).toHaveAttribute("data-state", "uploaded"));
    const [attemptId, questionId, blob] = vi.mocked(attemptsApi.uploadSpeakingAudio).mock.calls[0];
    expect([attemptId, questionId, (blob as Blob).type, (blob as Blob).size]).toEqual(["a1", "q1", "audio/webm", 64]);
    expect(onUploaded).toHaveBeenCalledWith("q1");
    expect(status()).toHaveTextContent("Yozuv saqlandi");
  });

  it("does not claim success when the upload fails, and allows retry", async () => {
    vi.mocked(attemptsApi.uploadSpeakingAudio)
      .mockRejectedValueOnce(new ApiError("Network", null, undefined))
      .mockResolvedValueOnce({ question_id: "q1", mime_type: "audio/webm", size_bytes: 64 });
    const { onUploaded } = setup();
    await recordOnce();
    fireEvent.click(screen.getByRole("button", { name: "Yozuvni yuborish" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Tarmoq xatosi");
    expect(root()).toHaveAttribute("data-state", "error");
    expect(onUploaded).not.toHaveBeenCalled();
    expect(screen.getByTestId("local-playback")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Qayta yuborish" }));
    await waitFor(() => expect(root()).toHaveAttribute("data-state", "uploaded"));
    expect(onUploaded).toHaveBeenCalledTimes(1);
  });

  it.each([
    [413, "juda katta"],
    [409, "Urinish faol emas"],
    [422, "Bu savol audio qabul qilmaydi"],
  ])("maps a %s server rejection to a clear message", async (code, text) => {
    vi.mocked(attemptsApi.uploadSpeakingAudio).mockRejectedValue(new ApiError("Bu savol audio qabul qilmaydi", null, code));
    setup();
    await recordOnce();
    fireEvent.click(screen.getByRole("button", { name: "Yozuvni yuborish" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(text);
  });

  it("rejects an oversized take before uploading", async () => {
    FakeRecorder.payloadSize = 20 * 1024 * 1024 + 1;
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Yozishni boshlash" }));
    await waitFor(() => expect(root()).toHaveAttribute("data-state", "recording"));
    fireEvent.click(screen.getByRole("button", { name: "To'xtatish" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("20 MB");
    expect(screen.queryByRole("button", { name: /yuborish/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Qayta yozish" })).toBeEnabled();
    expect(attemptsApi.uploadSpeakingAudio).not.toHaveBeenCalled();
  });

  it("can cancel an upload in progress without claiming it was saved", async () => {
    vi.mocked(attemptsApi.uploadSpeakingAudio).mockImplementation(
      (_a, _q, _b, opts) => new Promise((_res, rej) => opts?.signal?.addEventListener("abort", () => rej(new ApiError("canceled", null, undefined)))),
    );
    const { onUploaded } = setup();
    await recordOnce();
    fireEvent.click(screen.getByRole("button", { name: "Yozuvni yuborish" }));
    expect(root()).toHaveAttribute("data-state", "uploading");
    fireEvent.click(screen.getByRole("button", { name: "Bekor qilish" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("bekor qilindi");
    expect(onUploaded).not.toHaveBeenCalled();
  });

  it("re-records: a new take replaces the local one", async () => {
    setup();
    await recordOnce();
    expect(screen.getByTestId("local-playback")).toHaveAttribute("src", "blob:local-1");
    fireEvent.click(screen.getByRole("button", { name: "Qayta yozish" }));
    await waitFor(() => expect(root()).toHaveAttribute("data-state", "recording"));
    expect(screen.queryByTestId("local-playback")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "To'xtatish" }));
    await waitFor(() => expect(screen.getByTestId("local-playback")).toHaveAttribute("src", "blob:local-2"));
    expect(FakeRecorder.instances).toHaveLength(2);
  });

  it("plays a previously saved recording only through the authenticated fetch", async () => {
    vi.mocked(attemptsApi.getOwnSpeakingAudio).mockResolvedValue(new Blob(["x"], { type: "audio/webm" }));
    setup({ hasSavedAudio: true });
    expect(status()).toHaveTextContent("saqlangan");
    expect(attemptsApi.getOwnSpeakingAudio).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Saqlangan yozuvni tinglash" }));
    expect(await screen.findByTestId("saved-playback")).toHaveAttribute("src", "blob:local-1");
    expect(attemptsApi.getOwnSpeakingAudio).toHaveBeenCalledWith("a1", "q1");
    expect(screen.getByRole("button", { name: "Qayta yozish" })).toBeInTheDocument();
  });

  it("stops the microphone when unmounted mid-recording", async () => {
    const onUploaded = vi.fn();
    const { unmount } = render(<SpeakingRecorder attemptId="a1" questionId="q1" hasSavedAudio={false} onUploaded={onUploaded} />);
    fireEvent.click(screen.getByRole("button", { name: "Yozishni boshlash" }));
    await waitFor(() => expect(root()).toHaveAttribute("data-state", "recording"));
    unmount();
    expect(trackStop).toHaveBeenCalled();
    expect(FakeRecorder.instances[0].state).toBe("inactive");
    expect(attemptsApi.uploadSpeakingAudio).not.toHaveBeenCalled();
  });
});
