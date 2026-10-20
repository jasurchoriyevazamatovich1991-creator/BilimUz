/**
 * Task 3 — question-group media (IELTS Listening audio) in the attempt
 * UI. Same httpClient-spy style as the Task 1 media tests.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AttemptPage } from "./AttemptPage";
import { httpClient, type ApiEnvelope } from "@/api/client";
import type { AttemptDetailOut, QuestionForAttemptOut } from "@/api/attempts";

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

function q(id: string, text: string, extra: Partial<QuestionForAttemptOut> = {}): QuestionForAttemptOut {
  return {
    id, question_text: text, question_type: "single_choice", score: 1,
    options: [{ id: `${id}-o1`, option_text: "Alpha" }, { id: `${id}-o2`, option_text: "Beta" }],
    ...extra,
  };
}

const LISTENING_1 = { group_id: "g1", group_title: "Section 1", stimulus_text: null, group_media: [{ id: "gm1", media_type: "audio" }] };
const LISTENING_2 = { group_id: "g2", group_title: "Section 2", stimulus_text: null, group_media: [{ id: "gm2", media_type: "audio" }] };

function attemptWith(questions: QuestionForAttemptOut[]): AttemptDetailOut {
  return {
    id: "a1", test_id: "t1", status: "in_progress", start_time: "2026-01-01T00:00:00Z", expires_at: null, finish_time: null, questions,
    answered: questions.map((x) => ({ question_id: x.id, is_answered: false, selected_option: null, selected_options: null, text_answer: null })),
  };
}

const GROUP_URL = /^\/attempts\/a1\/group-media\/([^/]+)\/view-url$/;
const QUESTION_URL = /^\/attempts\/a1\/media\/([^/]+)\/view-url$/;

function mockGets(attempt: AttemptDetailOut, failing: string[] = []) {
  return vi.spyOn(httpClient, "get").mockImplementation((url: string) => {
    const g = GROUP_URL.exec(url) ?? QUESTION_URL.exec(url);
    if (g) {
      if (failing.includes(g[1])) return Promise.reject(new Error("409"));
      const kind = GROUP_URL.test(url) ? "group" : "question";
      const type = attempt.questions.flatMap((x) => [...(x.group_media ?? []), ...(x.media ?? [])]).find((m) => m.id === g[1])?.media_type ?? "audio";
      return Promise.resolve(envelope({ view_url: `https://signed.example.test/${kind}/${g[1]}`, media_type: type }));
    }
    return Promise.resolve(envelope(attempt));
  });
}

const calls = (spy: ReturnType<typeof mockGets>, re: RegExp) => spy.mock.calls.map((c) => c[0] as string).filter((u) => re.test(u));

describe("AttemptPage — Task 3 question-group media", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the group audio in the passage panel, even without stimulus text", async () => {
    const spy = mockGets(attemptWith([q("q1", "Where does the speaker live?", LISTENING_1)]));
    const { container } = renderPage();

    const panel = await screen.findByTestId("group-stimulus");
    expect(panel).toHaveTextContent("Section 1");
    await waitFor(() => expect(container.querySelector('audio[aria-label="Bo\'lim audio"]')).not.toBeNull());
    const audio = container.querySelector('audio[aria-label="Bo\'lim audio"]')!;
    expect(panel).toContainElement(audio as HTMLElement);
    expect(audio).toHaveAttribute("controls");
    expect(audio).toHaveAttribute("src", "https://signed.example.test/group/gm1");
    expect(calls(spy, GROUP_URL)).toEqual(["/attempts/a1/group-media/gm1/view-url"]);
  });

  it("keeps the same audio element mounted when moving between questions of the same group", async () => {
    const spy = mockGets(attemptWith([q("q1", "First Listening question", LISTENING_1), q("q2", "Second Listening question", LISTENING_1)]));
    const { container } = renderPage();

    await waitFor(() => expect(container.querySelector("audio")).not.toBeNull());
    const before = container.querySelector("audio");

    fireEvent.click(screen.getByRole("button", { name: /Keyingi/i }));
    await screen.findByText("Second Listening question");

    expect(container.querySelector("audio")).toBe(before);
    expect(calls(spy, GROUP_URL)).toHaveLength(1);
  });

  it("switches to the next group's audio when the group changes", async () => {
    mockGets(attemptWith([q("q1", "Part one", LISTENING_1), q("q2", "Part two", LISTENING_2)]));
    const { container } = renderPage();

    await waitFor(() => expect(container.querySelector("audio")).toHaveAttribute("src", "https://signed.example.test/group/gm1"));
    fireEvent.click(screen.getByRole("button", { name: /Keyingi/i }));
    await screen.findByText("Part two");
    await waitFor(() => expect(container.querySelector("audio")).toHaveAttribute("src", "https://signed.example.test/group/gm2"));
    expect(screen.getByTestId("group-stimulus")).toHaveTextContent("Section 2");
  });

  it("shows stimulus text and group audio together", async () => {
    mockGets(attemptWith([q("q1", "Passage question", { ...LISTENING_1, stimulus_text: "Listen and read along." })]));
    const { container } = renderPage();

    const panel = await screen.findByTestId("group-stimulus");
    expect(panel).toHaveTextContent("Listen and read along.");
    await waitFor(() => expect(container.querySelector("audio")).not.toBeNull());
  });

  it("missing audio: a group without media or stimulus shows no panel and makes no media request", async () => {
    const spy = mockGets(attemptWith([q("q1", "Grouped but empty", { group_id: "g9", group_title: "Empty", stimulus_text: null, group_media: [] })]));
    renderPage();

    await screen.findByText("Grouped but empty");
    expect(screen.queryByTestId("group-stimulus")).not.toBeInTheDocument();
    expect(calls(spy, GROUP_URL)).toEqual([]);
  });

  it("an older payload without group_media still renders the stimulus panel as before", async () => {
    const spy = mockGets(attemptWith([q("q1", "Reading question", { group_id: "g1", group_title: "Passage 1", stimulus_text: "Old passage text." })]));
    renderPage();

    expect(await screen.findByTestId("group-stimulus")).toHaveTextContent("Old passage text.");
    expect(screen.queryByTestId("group-media")).not.toBeInTheDocument();
    expect(calls(spy, GROUP_URL)).toEqual([]);
  });

  it("shows an accessible error with retry when the group audio cannot be authorized or loaded", async () => {
    const spy = mockGets(attemptWith([q("q1", "Forbidden audio question", LISTENING_1)]), ["gm1"]);
    renderPage();

    const alert = await screen.findByRole("alert", {}, { timeout: 4000 });
    expect(alert).toHaveTextContent("Bo'lim audio yuklanmadi.");
    const before = calls(spy, GROUP_URL).length;
    fireEvent.click(screen.getByRole("button", { name: "Qayta urinish" }));
    await waitFor(() => expect(calls(spy, GROUP_URL).length).toBeGreaterThan(before));
  });

  it("question-level media keeps using its own endpoint alongside group audio (Task 1 regression)", async () => {
    const spy = mockGets(attemptWith([q("q1", "Label the map", { ...LISTENING_1, media: [{ id: "qm1", media_type: "image", option_id: null }] })]));
    const { container } = renderPage();

    expect(await screen.findByRole("img", { name: "Savol rasm" })).toHaveAttribute("src", "https://signed.example.test/question/qm1");
    await waitFor(() => expect(container.querySelector("audio")).toHaveAttribute("src", "https://signed.example.test/group/gm1"));
    expect(calls(spy, QUESTION_URL)).toEqual(["/attempts/a1/media/qm1/view-url"]);
    expect(calls(spy, GROUP_URL)).toEqual(["/attempts/a1/group-media/gm1/view-url"]);
  });

  it("answer selection still saves while group audio is present", async () => {
    mockGets(attemptWith([q("q1", "Choose one", LISTENING_1)]));
    const patch = vi.spyOn(httpClient, "patch").mockResolvedValue(envelope(null));
    renderPage();

    await screen.findByText("Choose one");
    fireEvent.click(screen.getAllByRole("radio")[0]);
    await waitFor(() => expect(patch).toHaveBeenCalledWith("/attempts/a1/answer", expect.objectContaining({ question_id: "q1", selected_option: "q1-o1" })));
  });
});
