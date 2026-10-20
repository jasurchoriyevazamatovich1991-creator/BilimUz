/**
 * Task 1 (IELTS/SAT/GRE audit) — question/option media during an
 * attempt. Same httpClient-spy style as the other AttemptPage test
 * files: the real attemptsApi/useAttempt/AttemptMediaList code runs
 * against a stubbed HTTP layer.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AttemptPage } from "./AttemptPage";
import { httpClient, type ApiEnvelope } from "@/api/client";
import type { AttemptDetailOut, AttemptMediaOut, QuestionForAttemptOut } from "@/api/attempts";

function envelope<T>(data: T): { data: ApiEnvelope<T> } {
  return { data: { success: true, message: "OK", data, errors: null } };
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/student/tests/t1/attempt/a1"]}>
        <Routes>
          <Route path="/student/tests/:testId/attempt/:attemptId" element={<AttemptPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function question(id: string, text: string, media?: AttemptMediaOut[]): QuestionForAttemptOut {
  return {
    id, question_text: text, question_type: "single_choice", score: 1,
    options: [{ id: `${id}-o1`, option_text: "Alpha" }, { id: `${id}-o2`, option_text: "Beta" }],
    ...(media ? { media } : {}),
  };
}

function attemptWith(questions: QuestionForAttemptOut[]): AttemptDetailOut {
  return {
    id: "a1", test_id: "t1", status: "in_progress", start_time: "2026-01-01T00:00:00Z",
    expires_at: null, finish_time: null, questions,
    answered: questions.map((q) => ({ question_id: q.id, is_answered: false, selected_option: null, selected_options: null, text_answer: null })),
  };
}

const VIEW_URL = /^\/attempts\/a1\/media\/([^/]+)\/view-url$/;

/** Routes GET calls: the attempt detail, and view-url per media id.
 * `failing` media ids reject like a backend 404/409. */
function mockGets(attempt: AttemptDetailOut, failing: string[] = []) {
  return vi.spyOn(httpClient, "get").mockImplementation((url: string) => {
    const m = VIEW_URL.exec(url);
    if (m) {
      const mediaId = m[1];
      if (failing.includes(mediaId)) return Promise.reject(new Error("409"));
      const item = attempt.questions.flatMap((q) => q.media ?? []).find((x) => x.id === mediaId);
      return Promise.resolve(envelope({ view_url: `https://signed.example.test/${mediaId}`, media_type: item?.media_type ?? "image" }));
    }
    return Promise.resolve(envelope(attempt));
  });
}

function viewUrlCalls(spy: ReturnType<typeof mockGets>) {
  return spy.mock.calls.map((c) => c[0] as string).filter((u) => VIEW_URL.test(u));
}

describe("AttemptPage — Task 1 media delivery", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("question without media renders no media block and requests no view URL", async () => {
    const spy = mockGets(attemptWith([question("q1", "Plain question")]));
    renderPage();

    await screen.findByText("Plain question");
    expect(screen.queryByTestId("attempt-media")).not.toBeInTheDocument();
    expect(viewUrlCalls(spy)).toEqual([]);
  });

  it("renders a question image with an accessible alt text from the signed URL", async () => {
    mockGets(attemptWith([question("q1", "Look at the chart", [{ id: "m-img", media_type: "image", option_id: null }])]));
    renderPage();

    const img = await screen.findByRole("img", { name: "Savol rasm" });
    expect(img).toHaveAttribute("src", "https://signed.example.test/m-img");
  });

  it("renders question audio with native controls and an accessible label", async () => {
    mockGets(attemptWith([question("q1", "Listen and answer", [{ id: "m-aud", media_type: "audio", option_id: null }])]));
    const { container } = renderPage();

    await waitFor(() => expect(container.querySelector("audio")).not.toBeNull());
    const audio = container.querySelector("audio")!;
    expect(audio).toHaveAttribute("controls");
    expect(audio).toHaveAttribute("aria-label", "Savol audio");
    expect(audio).toHaveAttribute("src", "https://signed.example.test/m-aud");
    expect(audio).toHaveAttribute("preload", "metadata");
  });

  it("renders every supported media type, numbering labels when there are several", async () => {
    const media: AttemptMediaOut[] = [
      { id: "m1", media_type: "image", option_id: null },
      { id: "m2", media_type: "audio", option_id: null },
      { id: "m3", media_type: "video", option_id: null },
      { id: "m4", media_type: "formula", option_id: null },
    ];
    mockGets(attemptWith([question("q1", "Mixed media", media)]));
    const page = renderPage();

    expect(await screen.findByRole("img", { name: "Savol rasm 1" })).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: "Savol formula 4" })).toBeInTheDocument();
    await waitFor(() => expect(page.container.querySelector('audio[aria-label="Savol audio 2"]')).not.toBeNull());
    expect(page.container.querySelector('video[aria-label="Savol video 3"]')).not.toBeNull();
  });

  it("shows a loading state while the view URL is pending", async () => {
    const attempt = attemptWith([question("q1", "Pending media", [{ id: "m-slow", media_type: "image", option_id: null }])]);
    vi.spyOn(httpClient, "get").mockImplementation((url: string) =>
      VIEW_URL.test(url) ? new Promise(() => {}) : Promise.resolve(envelope(attempt)),
    );
    renderPage();

    expect(await screen.findByRole("status")).toHaveTextContent("Savol rasm yuklanmoqda...");
  });

  it("shows an error with a working retry when the view URL request fails", async () => {
    const attempt = attemptWith([question("q1", "Broken media", [{ id: "m-bad", media_type: "audio", option_id: null }])]);
    const spy = mockGets(attempt, ["m-bad"]);
    renderPage();

    // AttemptMediaItem retries a failed view-URL request once (with
    // React Query's ~1s backoff) before showing the error.
    const alert = await screen.findByRole("alert", {}, { timeout: 4000 });
    expect(alert).toHaveTextContent("Savol audio yuklanmadi.");
    const before = viewUrlCalls(spy).length;

    fireEvent.click(screen.getByRole("button", { name: "Qayta urinish" }));
    await waitFor(() => expect(viewUrlCalls(spy).length).toBeGreaterThan(before));
  });

  it("shows an error when the browser cannot load the file (e.g. expired URL) and retries with a fresh URL", async () => {
    const spy = mockGets(attemptWith([question("q1", "Expiring image", [{ id: "m-exp", media_type: "image", option_id: null }])]));
    renderPage();

    const img = await screen.findByRole("img", { name: "Savol rasm" });
    const before = viewUrlCalls(spy).length;
    fireEvent.error(img);

    expect(await screen.findByRole("alert")).toHaveTextContent("Savol rasm yuklanmadi.");
    fireEvent.click(screen.getByRole("button", { name: "Qayta urinish" }));
    await waitFor(() => expect(viewUrlCalls(spy).length).toBeGreaterThan(before));
    expect(await screen.findByRole("img", { name: "Savol rasm" })).toBeInTheDocument();
  });

  it("renders option media next to its option, outside the clickable label", async () => {
    const q = question("q1", "Pick the picture", [{ id: "m-opt", media_type: "audio", option_id: "q1-o2" }]);
    const patchSpy = vi.spyOn(httpClient, "patch");
    const { container } = (mockGets(attemptWith([q])), renderPage());

    await waitFor(() => expect(container.querySelector('audio[aria-label="Variant audio"]')).not.toBeNull());
    const audio = container.querySelector('audio[aria-label="Variant audio"]')!;
    expect(audio.closest("label")).toBeNull();

    fireEvent.click(audio);
    const radios = screen.getAllByRole("radio");
    expect(radios.every((r) => !(r as HTMLInputElement).checked)).toBe(true);
    expect(patchSpy).not.toHaveBeenCalled();
  });

  it("only requests media for the question on screen, and switches media on navigation", async () => {
    const q1 = question("q1", "First question", [{ id: "m-a", media_type: "image", option_id: null }]);
    const q2 = question("q2", "Second question", [{ id: "m-b", media_type: "image", option_id: null }]);
    const spy = mockGets(attemptWith([q1, q2]));
    renderPage();

    expect(await screen.findByRole("img", { name: "Savol rasm" })).toHaveAttribute("src", "https://signed.example.test/m-a");
    expect(viewUrlCalls(spy)).toEqual(["/attempts/a1/media/m-a/view-url"]);

    fireEvent.click(screen.getByRole("button", { name: /Keyingi/i }));
    await screen.findByText("Second question");
    await waitFor(() => expect(screen.getByRole("img", { name: "Savol rasm" })).toHaveAttribute("src", "https://signed.example.test/m-b"));
  });

  it("an attempt payload without the media field (older backend) still renders normally", async () => {
    const spy = mockGets(attemptWith([question("q1", "Legacy payload question")]));
    renderPage();

    await screen.findByText("Legacy payload question");
    expect(screen.getAllByRole("radio")).toHaveLength(2);
    expect(viewUrlCalls(spy)).toEqual([]);
  });
});
