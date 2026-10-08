/**
 * Sprint 80 — Student RichText / LaTeX Rendering.
 * Same httpClient-spy style as this page's own pre-existing
 * AttemptPage.test.tsx/sprint76/sprint77 test files — lets the REAL
 * attemptsApi/useAttempt code run against a stubbed HTTP layer.
 *
 * Covers (task spec section 9): plain text renders, inline LaTeX
 * renders, block LaTeX renders, option LaTeX renders, group stimulus
 * LaTeX renders, short_answer/essay submitted text behavior remains
 * correct, modular/legacy AttemptPage behavior remains correct, and
 * the security requirements (malicious HTML/script not executed,
 * javascript URL not executed, event handler injection blocked).
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AttemptPage } from "./AttemptPage";
import { httpClient, type ApiEnvelope } from "@/api/client";
import type { AttemptDetailOut } from "@/api/attempts";

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

function makeAttempt(overrides: Partial<AttemptDetailOut> = {}): AttemptDetailOut {
  return {
    id: "a1",
    test_id: "t1",
    status: "in_progress",
    start_time: "2026-01-01T00:00:00Z",
    expires_at: null,
    finish_time: null,
    questions: [],
    answered: [],
    ...overrides,
  };
}

describe("AttemptPage — Sprint 80 RichText/LaTeX rendering", () => {
  it("1. plain text question_text/option_text renders exactly as before (no stray KaTeX markup)", async () => {
    const PLAIN_Q = {
      id: "q1", question_text: "Poytaxt qaysi shahar?", question_type: "single_choice", score: 1,
      options: [{ id: "o1", option_text: "Toshkent" }, { id: "o2", option_text: "Samarqand" }],
    };
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(makeAttempt({ questions: [PLAIN_Q], answered: [{ question_id: "q1", is_answered: false, selected_option: null, selected_options: null, text_answer: null }] })),
    );
    renderPage();

    await waitFor(() => expect(screen.getByText("Poytaxt qaysi shahar?")).toBeInTheDocument());
    expect(screen.getByText("Toshkent")).toBeInTheDocument();
    expect(document.querySelector(".katex")).not.toBeInTheDocument();
  });

  it("2. inline LaTeX ($...$) in question_text renders via KaTeX", async () => {
    const Q = {
      id: "q1", question_text: "Hisoblang: $F = ma$", question_type: "single_choice", score: 1,
      options: [{ id: "o1", option_text: "A" }, { id: "o2", option_text: "B" }],
    };
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(makeAttempt({ questions: [Q], answered: [{ question_id: "q1", is_answered: false, selected_option: null, selected_options: null, text_answer: null }] })),
    );
    renderPage();

    await waitFor(() => expect(document.querySelector(".katex")).toBeInTheDocument());
    expect(document.querySelector(".katex-display")).not.toBeInTheDocument();
  });

  it("3. block LaTeX ($$...$$) in question_text renders via KaTeX in display mode", async () => {
    const Q = {
      id: "q1", question_text: "Formula: $$v^2 = v_0^2 + 2as$$", question_type: "single_choice", score: 1,
      options: [{ id: "o1", option_text: "A" }, { id: "o2", option_text: "B" }],
    };
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(makeAttempt({ questions: [Q], answered: [{ question_id: "q1", is_answered: false, selected_option: null, selected_options: null, text_answer: null }] })),
    );
    renderPage();

    await waitFor(() => expect(document.querySelector(".katex-display")).toBeInTheDocument());
  });

  it("4. option LaTeX renders via KaTeX", async () => {
    const Q = {
      id: "q1", question_text: "Tezlikni toping", question_type: "single_choice", score: 1,
      options: [{ id: "o1", option_text: "$v = \\frac{s}{t}$" }, { id: "o2", option_text: "B" }],
    };
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(makeAttempt({ questions: [Q], answered: [{ question_id: "q1", is_answered: false, selected_option: null, selected_options: null, text_answer: null }] })),
    );
    renderPage();

    await waitFor(() => expect(document.querySelector(".katex")).toBeInTheDocument());
  });

  it("5. group stimulus_text LaTeX renders via KaTeX", async () => {
    const Q = {
      id: "q1", question_text: "Passage question", question_type: "single_choice", score: 1,
      options: [{ id: "o1", option_text: "A" }, { id: "o2", option_text: "B" }],
      group_id: "grp-1", group_title: "Passage 1", stimulus_text: "Given $E = mc^2$, find...",
    };
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(makeAttempt({ questions: [Q], answered: [{ question_id: "q1", is_answered: false, selected_option: null, selected_options: null, text_answer: null }] })),
    );
    renderPage();

    const panel = await screen.findByTestId("group-stimulus");
    await waitFor(() => expect(panel.querySelector(".katex")).toBeInTheDocument());
    expect(panel).toHaveTextContent("Passage 1");
  });

  it("6. short_answer submitted text behavior remains correct (plain input, not routed through FormulaText)", async () => {
    const Q = { id: "q1", question_text: "Savol", question_type: "short_answer", score: 1, options: [] };
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(makeAttempt({ questions: [Q], answered: [{ question_id: "q1", is_answered: true, selected_option: null, selected_options: null, text_answer: "$F = ma$" }] })),
    );
    renderPage();

    await waitFor(() => expect(screen.getByPlaceholderText("Javobingizni shu yerga yozing...")).toHaveValue("$F = ma$"));
    // The literal $-delimited text is preserved verbatim in the input
    // value, not run through KaTeX anywhere on the page.
    expect(document.querySelector(".katex")).not.toBeInTheDocument();
  });

  it("7. essay submitted text behavior remains correct (plain textarea, not routed through FormulaText)", async () => {
    const Q = { id: "q1", question_text: "Insho yozing", question_type: "essay", score: 5, options: [] };
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(makeAttempt({ questions: [Q], answered: [{ question_id: "q1", is_answered: true, selected_option: null, selected_options: null, text_answer: "Essay with $ sign but not math" }] })),
    );
    renderPage();

    await waitFor(() => expect(screen.getByPlaceholderText("Javobingizni shu yerga yozing...")).toHaveValue("Essay with $ sign but not math"));
    expect(document.querySelector(".katex")).not.toBeInTheDocument();
  });

  // --- Security ---

  it("8. a <script> tag embedded in question_text is never executed", async () => {
    const Q = {
      id: "q1", question_text: "<script>window.__attemptXss = true</script>Savol matni", question_type: "single_choice", score: 1,
      options: [{ id: "o1", option_text: "A" }, { id: "o2", option_text: "B" }],
    };
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(makeAttempt({ questions: [Q], answered: [{ question_id: "q1", is_answered: false, selected_option: null, selected_options: null, text_answer: null }] })),
    );
    renderPage();

    // A <script> tag inserted via dangerouslySetInnerHTML is parsed into
    // the DOM (browser/jsdom-spec behavior) but is never EXECUTED that
    // way — what matters is that it never runs.
    await waitFor(() => expect(screen.getByText(/Savol matni/)).toBeInTheDocument());
    expect((window as unknown as { __attemptXss?: boolean }).__attemptXss).toBeUndefined();
  });

  it("9. a javascript: URL never reaches a live, clickable href (backend bleach already strips the href attribute before this text reaches the frontend — see sanitize_rich_text's own test_javascript_protocol_link_is_stripped; this asserts the frontend doesn't re-introduce one for already-sanitized content)", async () => {
    const Q = {
      id: "q1", question_text: "Savol", question_type: "single_choice", score: 1,
      // Already-sanitized shape (bleach strips the disallowed-protocol
      // href attribute but keeps the <a> tag itself, per the backend's
      // own test_javascript_protocol_link_is_stripped).
      options: [{ id: "o1", option_text: "<a>link</a>" }, { id: "o2", option_text: "B" }],
    };
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(makeAttempt({ questions: [Q], answered: [{ question_id: "q1", is_answered: false, selected_option: null, selected_options: null, text_answer: null }] })),
    );
    renderPage();

    await waitFor(() => expect(screen.getByText("Savol")).toBeInTheDocument());
    const anchor = document.querySelector("a");
    expect(anchor).toBeInTheDocument();
    expect(anchor?.getAttribute("href")).toBeNull();
  });

  it("10. an event-handler attribute embedded in question_text does not execute on render", async () => {
    const Q = {
      id: "q1", question_text: '<img src="x" onerror="window.__attemptXss2 = true" />Hodisa matni', question_type: "single_choice", score: 1,
      options: [{ id: "o1", option_text: "A" }, { id: "o2", option_text: "B" }],
    };
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(makeAttempt({ questions: [Q], answered: [{ question_id: "q1", is_answered: false, selected_option: null, selected_options: null, text_answer: null }] })),
    );
    renderPage();

    await waitFor(() => expect(screen.getByText(/Hodisa matni/)).toBeInTheDocument());
    expect((window as unknown as { __attemptXss2?: boolean }).__attemptXss2).toBeUndefined();
  });

  // --- Regression: existing question-type rendering remains correct ---

  it("11. multiple_choice checkboxes still render/toggle correctly alongside FormulaText rendering", async () => {
    const Q = {
      id: "q1", question_text: "Ranglarni tanlang", question_type: "multiple_choice", score: 1,
      options: [{ id: "o1", option_text: "Qizil" }, { id: "o2", option_text: "Ko'k" }],
    };
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(makeAttempt({ questions: [Q], answered: [{ question_id: "q1", is_answered: false, selected_option: null, selected_options: null, text_answer: null }] })),
    );
    const patchSpy = vi.spyOn(httpClient, "patch").mockResolvedValue(envelope(null));
    renderPage();

    await waitFor(() => expect(screen.getByText("Qizil")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Qizil").closest("label")!.querySelector("input")!);
    await waitFor(() => expect(patchSpy).toHaveBeenCalledWith("/attempts/a1/answer", { question_id: "q1", selected_options: ["o1"] }));
  });
});
