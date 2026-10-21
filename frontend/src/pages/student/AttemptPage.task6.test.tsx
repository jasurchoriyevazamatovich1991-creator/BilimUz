/**
 * Task 6 — mark for review, calculator and Speaking recorder in the
 * attempt screen. Same httpClient-spy style as the Task 1/3 tests.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

const choice = (id: string, extra: Partial<QuestionForAttemptOut> = {}): QuestionForAttemptOut => ({
  id, question_text: `Question ${id}`, question_type: "single_choice", score: 1,
  options: [{ id: `${id}-o1`, option_text: "Alpha" }, { id: `${id}-o2`, option_text: "Beta" }], ...extra,
});
const essay = (id: string, extra: Partial<QuestionForAttemptOut> = {}): QuestionForAttemptOut => ({
  id, question_text: `Prompt ${id}`, question_type: "essay", score: 1, options: [], ...extra,
});

function attempt(questions: QuestionForAttemptOut[], over: Partial<AttemptDetailOut> = {}): AttemptDetailOut {
  return {
    id: "a1", test_id: "t1", status: "in_progress", start_time: "2026-01-01T00:00:00Z",
    expires_at: new Date(Date.now() + 30 * 60_000).toISOString(), finish_time: null, questions,
    answered: questions.map((q) => ({ question_id: q.id, is_answered: false, selected_option: null, selected_options: null, text_answer: null })),
    marked_question_ids: [], ...over,
  };
}

function mockApi(detail: AttemptDetailOut) {
  const get = vi.spyOn(httpClient, "get").mockResolvedValue(envelope(detail));
  const put = vi.spyOn(httpClient, "put").mockImplementation((url: string, body: unknown) => {
    const qid = url.split("/").pop() as string;
    const marked = (body as { marked: boolean }).marked;
    const current = new Set(detail.marked_question_ids ?? []);
    if (marked) current.add(qid); else current.delete(qid);
    detail.marked_question_ids = [...current];
    return Promise.resolve(envelope({ question_id: qid, marked, marked_question_ids: [...current] }));
  });
  const patch = vi.spyOn(httpClient, "patch").mockResolvedValue(envelope(null));
  const post = vi.spyOn(httpClient, "post");
  return { get, put, patch, post };
}

const navButton = (n: number) => screen.getByRole("button", { name: new RegExp(`^Savol ${n}:`) });

describe("AttemptPage — Task 6", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("restores the four navigation states from the server", async () => {
    const qs = [choice("q1"), choice("q2"), choice("q3"), choice("q4")];
    const detail = attempt(qs, { marked_question_ids: ["q3", "q4"] });
    detail.answered[1] = { ...detail.answered[1], is_answered: true, selected_option: "q2-o1" };
    detail.answered[3] = { ...detail.answered[3], is_answered: true, selected_option: "q4-o2" };
    mockApi(detail);
    renderPage();
    await screen.findByText("Question q1");
    fireEvent.click(navButton(2)); // move "current" off question 1 so its own state is visible
    expect(navButton(1)).toHaveAttribute("data-state", "unanswered");
    expect(navButton(2)).toHaveAttribute("data-state", "answered");
    expect(navButton(3)).toHaveAttribute("data-state", "marked");
    expect(navButton(4)).toHaveAttribute("data-state", "answered_marked");
    fireEvent.click(navButton(4));
    expect(screen.getByRole("button", { name: /Belgilangan — belgini olib tashlash/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("radio", { name: "Beta" })).toBeChecked();
  });

  it("toggling the review mark calls only the review endpoint and keeps the answer", async () => {
    const qs = [choice("q1"), choice("q2")];
    const detail = attempt(qs);
    detail.answered[0] = { ...detail.answered[0], is_answered: true, selected_option: "q1-o1" };
    const { put, patch, post } = mockApi(detail);
    renderPage();
    await screen.findByText("Question q1");

    fireEvent.click(screen.getByRole("button", { name: "⚐ Ko'rib chiqish uchun belgilash" }));
    await waitFor(() => expect(put).toHaveBeenCalledWith("/attempts/a1/review-marks/q1", { marked: true }));
    expect(await screen.findByRole("button", { name: /Belgilangan/ })).toHaveAttribute("aria-pressed", "true");
    expect(patch).not.toHaveBeenCalled();
    expect(post).not.toHaveBeenCalled();
    expect(screen.getByRole("radio", { name: "Alpha" })).toBeChecked();

    fireEvent.click(navButton(2));
    expect(navButton(1)).toHaveAttribute("data-state", "answered_marked");
    fireEvent.click(navButton(1));
    fireEvent.click(screen.getByRole("button", { name: /Belgilangan — belgini olib tashlash/ }));
    await waitFor(() => expect(put).toHaveBeenLastCalledWith("/attempts/a1/review-marks/q1", { marked: false }));
    await waitFor(() => expect(screen.getByRole("button", { name: "⚐ Ko'rib chiqish uchun belgilash" })).toBeInTheDocument());
    expect(patch).not.toHaveBeenCalled();
  });

  it("offers the calculator only where the section allows it, without touching answers or the timer", async () => {
    const qs = [choice("q1", { calculator_enabled: true }), essay("q2")];
    const detail = attempt(qs);
    const { patch, put, post } = mockApi(detail);
    renderPage();
    await screen.findByText("Question q1");
    const timerText = screen.getByText(/^\d+:\d{2}$/).textContent;

    fireEvent.click(screen.getByRole("radio", { name: "Beta" }));
    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("button", { name: /Kalkulyator/ }));
    const calc = screen.getByRole("dialog", { name: "Kalkulyator" });
    for (const key of ["7", "*", "6", "Enter"]) fireEvent.keyDown(calc, { key });
    expect(within(calc).getByTestId("calc-display")).toHaveTextContent("42");
    fireEvent.click(within(calc).getByRole("button", { name: "Kalkulyatorni yopish" }));
    expect(screen.queryByRole("dialog", { name: "Kalkulyator" })).not.toBeInTheDocument();

    expect(screen.getByText("Question q1")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Beta" })).toBeChecked();
    expect(patch).toHaveBeenCalledTimes(1);
    expect(put).not.toHaveBeenCalled();
    expect(post).not.toHaveBeenCalled();
    expect(screen.getByText(/^\d+:\d{2}$/).textContent).toBe(timerText);

    // Not offered on a section without the flag.
    fireEvent.click(navButton(2));
    expect(screen.queryByRole("button", { name: /Kalkulyator/ })).not.toBeInTheDocument();
  });

  it("closes the calculator when moving to a question whose section disallows it", async () => {
    mockApi(attempt([choice("q1", { calculator_enabled: true }), choice("q2")]));
    renderPage();
    await screen.findByText("Question q1");
    fireEvent.click(screen.getByRole("button", { name: /Kalkulyator/ }));
    expect(screen.getByRole("dialog", { name: "Kalkulyator" })).toBeInTheDocument();
    fireEvent.click(navButton(2));
    expect(screen.queryByRole("dialog", { name: "Kalkulyator" })).not.toBeInTheDocument();
  });

  it("shows the recorder only for Speaking questions and keeps the text field", async () => {
    const qs = [essay("q1", { accepts_audio: true }), essay("q2")];
    const detail = attempt(qs);
    detail.answered[0] = { ...detail.answered[0], is_answered: true, text_answer: "my notes", has_audio: true };
    mockApi(detail);
    renderPage();
    await screen.findByText("Prompt q1");
    expect(screen.getByTestId("speaking-recorder")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Javobingizni shu yerga yozing...")).toHaveValue("my notes");
    fireEvent.click(navButton(2));
    expect(screen.queryByTestId("speaking-recorder")).not.toBeInTheDocument();
    expect(navButton(1)).toHaveAttribute("data-state", "answered");
  });

  it("counts a recording-only Speaking response as answered", async () => {
    const qs = [essay("q1", { accepts_audio: true }), essay("q2")];
    const detail = attempt(qs);
    detail.answered[0] = { ...detail.answered[0], is_answered: true, has_audio: true };
    mockApi(detail);
    renderPage();
    await screen.findByText("Prompt q1");
    fireEvent.click(navButton(2));
    expect(navButton(1)).toHaveAttribute("data-state", "answered");
  });
});
