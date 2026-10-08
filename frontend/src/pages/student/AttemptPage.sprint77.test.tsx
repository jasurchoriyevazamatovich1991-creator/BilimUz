/**
 * Sprint 77 — QuestionGroup / stimulus_text student exam delivery.
 * Same httpClient-spy style as this page's own pre-existing
 * AttemptPage.test.tsx/AttemptPage.sprint76.test.tsx — lets the REAL
 * attemptsApi/useAttempt code run against a stubbed HTTP layer.
 *
 * Covers (Sprint 77 task's Phase 12 list): grouped question renders
 * stimulus, stimulus shown once per screen, two questions sharing a
 * group, group transition, ungrouped question, null stimulus,
 * multiple groups, refresh/resume, modular exam, non-modular exam,
 * future module not shown, existing question types unaffected.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AttemptPage } from "./AttemptPage";
import { httpClient, type ApiEnvelope } from "@/api/client";
import type { AttemptDetailOut, ModuleForAttemptOut } from "@/api/attempts";

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

const GROUPED_Q1 = {
  id: "q-g1a", question_text: "Passage question 1", question_type: "single_choice", score: 1,
  options: [{ id: "o-a", option_text: "A" }, { id: "o-b", option_text: "B" }],
  group_id: "grp-1", group_title: "Passage 1", stimulus_text: "Once upon a time, in a faraway land...",
};
const GROUPED_Q2 = {
  id: "q-g1b", question_text: "Passage question 2", question_type: "single_choice", score: 1,
  options: [{ id: "o-c", option_text: "C" }, { id: "o-d", option_text: "D" }],
  group_id: "grp-1", group_title: "Passage 1", stimulus_text: "Once upon a time, in a faraway land...",
};
const GROUP2_Q = {
  id: "q-g2a", question_text: "Second passage question", question_type: "single_choice", score: 1,
  options: [{ id: "o-e", option_text: "E" }, { id: "o-f", option_text: "F" }],
  group_id: "grp-2", group_title: "Passage 2", stimulus_text: "A second, different passage.",
};
const UNGROUPED_Q = {
  id: "q-plain", question_text: "A plain standalone question", question_type: "single_choice", score: 1,
  options: [{ id: "o-g", option_text: "G" }, { id: "o-h", option_text: "H" }],
};
const NULL_STIMULUS_Q = {
  id: "q-nullstim", question_text: "Diagram-only group question", question_type: "single_choice", score: 1,
  options: [{ id: "o-i", option_text: "I" }, { id: "o-j", option_text: "J" }],
  group_id: "grp-3", group_title: "Diagram set", stimulus_text: null,
};

function makeAttempt(overrides: Partial<AttemptDetailOut> = {}): AttemptDetailOut {
  return {
    id: "a1",
    test_id: "t1",
    status: "in_progress",
    start_time: "2026-01-01T00:00:00Z",
    expires_at: null,
    finish_time: null,
    questions: [GROUPED_Q1],
    answered: [{ question_id: GROUPED_Q1.id, is_answered: false, selected_option: null, selected_options: null, text_answer: null }],
    ...overrides,
  };
}

function answeredFor(questions: Array<{ id: string }>) {
  return questions.map((q) => ({ question_id: q.id, is_answered: false, selected_option: null, selected_options: null, text_answer: null }));
}

const MODULE1_INFO: ModuleForAttemptOut = {
  id: "m1", name: "Modul 1", order_number: 0, duration: 10,
  section_id: "s1", section_name: "Reading", section_order_number: 0,
};

describe("AttemptPage — Sprint 77 QuestionGroup/stimulus_text delivery", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the stimulus for a grouped question", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(envelope(makeAttempt()));
    renderPage();

    const panel = await screen.findByTestId("group-stimulus");
    expect(panel).toHaveTextContent("Once upon a time, in a faraway land...");
    expect(panel).toHaveTextContent("Passage 1");
  });

  it("shows the stimulus exactly once on screen (not duplicated)", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(envelope(makeAttempt()));
    renderPage();

    await screen.findByTestId("group-stimulus");
    expect(screen.getAllByText("Once upon a time, in a faraway land...")).toHaveLength(1);
  });

  it("two questions in the same group both show the identical stimulus when navigated between", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(makeAttempt({ questions: [GROUPED_Q1, GROUPED_Q2], answered: answeredFor([GROUPED_Q1, GROUPED_Q2]) })),
    );
    renderPage();

    await waitFor(() => expect(screen.getByText("Passage question 1")).toBeInTheDocument());
    expect(screen.getByTestId("group-stimulus")).toHaveTextContent("Once upon a time");

    fireEvent.click(screen.getByRole("button", { name: /Keyingi/i }));

    await waitFor(() => expect(screen.getByText("Passage question 2")).toBeInTheDocument());
    expect(screen.getByTestId("group-stimulus")).toHaveTextContent("Once upon a time");
  });

  it("group transition: moving from group 1 to group 2 updates the stimulus panel", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(makeAttempt({ questions: [GROUPED_Q1, GROUP2_Q], answered: answeredFor([GROUPED_Q1, GROUP2_Q]) })),
    );
    renderPage();

    await waitFor(() => expect(screen.getByText("Passage question 1")).toBeInTheDocument());
    expect(screen.getByTestId("group-stimulus")).toHaveTextContent("Once upon a time");

    fireEvent.click(screen.getByRole("button", { name: /Keyingi/i }));

    await waitFor(() => expect(screen.getByText("Second passage question")).toBeInTheDocument());
    expect(screen.getByTestId("group-stimulus")).toHaveTextContent("A second, different passage.");
  });

  it("group to ungrouped transition: no stimulus panel for an ungrouped question", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(makeAttempt({ questions: [GROUPED_Q1, UNGROUPED_Q], answered: answeredFor([GROUPED_Q1, UNGROUPED_Q]) })),
    );
    renderPage();

    await waitFor(() => expect(screen.getByText("Passage question 1")).toBeInTheDocument());
    expect(screen.getByTestId("group-stimulus")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Keyingi/i }));

    await waitFor(() => expect(screen.getByText("A plain standalone question")).toBeInTheDocument());
    expect(screen.queryByTestId("group-stimulus")).not.toBeInTheDocument();
  });

  it("renders no stimulus panel at all for a fully ungrouped attempt", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(makeAttempt({ questions: [UNGROUPED_Q], answered: answeredFor([UNGROUPED_Q]) })),
    );
    renderPage();

    await waitFor(() => expect(screen.getByText("A plain standalone question")).toBeInTheDocument());
    expect(screen.queryByTestId("group-stimulus")).not.toBeInTheDocument();
  });

  it("a grouped question with null stimulus_text renders no stimulus panel", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(makeAttempt({ questions: [NULL_STIMULUS_Q], answered: answeredFor([NULL_STIMULUS_Q]) })),
    );
    renderPage();

    await waitFor(() => expect(screen.getByText("Diagram-only group question")).toBeInTheDocument());
    expect(screen.queryByTestId("group-stimulus")).not.toBeInTheDocument();
  });

  it("multiple distinct groups each render their own stimulus correctly", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(makeAttempt({ questions: [GROUPED_Q1, GROUP2_Q, UNGROUPED_Q], answered: answeredFor([GROUPED_Q1, GROUP2_Q, UNGROUPED_Q]) })),
    );
    renderPage();

    await waitFor(() => expect(screen.getByText("Passage question 1")).toBeInTheDocument());
    expect(screen.getByTestId("group-stimulus")).toHaveTextContent("Once upon a time");
    fireEvent.click(screen.getByRole("button", { name: /Keyingi/i }));
    await waitFor(() => expect(screen.getByText("Second passage question")).toBeInTheDocument());
    expect(screen.getByTestId("group-stimulus")).toHaveTextContent("A second, different passage.");
    fireEvent.click(screen.getByRole("button", { name: /Keyingi/i }));
    await waitFor(() => expect(screen.getByText("A plain standalone question")).toBeInTheDocument());
    expect(screen.queryByTestId("group-stimulus")).not.toBeInTheDocument();
  });

  it("resume: reloading mid-attempt shows the same stimulus for the same active question", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(envelope(makeAttempt()));
    const { unmount } = renderPage();
    await screen.findByTestId("group-stimulus");
    unmount();

    renderPage();
    const panel = await screen.findByTestId("group-stimulus");
    expect(panel).toHaveTextContent("Once upon a time, in a faraway land...");
  });

  it("works for a modular exam — group context shown for the active module's question", async () => {
    vi.spyOn(httpClient, "get").mockImplementation(async (url: string) => {
      if (url.includes("/modules/")) return envelope(MODULE1_INFO);
      return envelope(
        makeAttempt({
          module_id: "m1",
          module_expires_at: new Date(Date.now() + 10 * 60 * 1000).toISOString(),
          questions: [GROUPED_Q1],
          answered: answeredFor([GROUPED_Q1]),
        }),
      );
    });
    renderPage();

    await screen.findByTestId("module-navigator");
    const panel = await screen.findByTestId("group-stimulus");
    expect(panel).toHaveTextContent("Once upon a time");
  });

  it("a future module's group stimulus is never requested/rendered (backend scoping relied on, no client leak surface)", async () => {
    const getSpy = vi.spyOn(httpClient, "get").mockImplementation(async (url: string) => {
      if (url.includes("/modules/")) return envelope(MODULE1_INFO);
      // Backend's effective_question_order already excludes future-module
      // questions entirely — this attempt simply never contains GROUP2_Q
      // while module 1 is active, by construction.
      return envelope(
        makeAttempt({
          module_id: "m1",
          module_expires_at: new Date(Date.now() + 10 * 60 * 1000).toISOString(),
          questions: [GROUPED_Q1],
          answered: answeredFor([GROUPED_Q1]),
        }),
      );
    });
    renderPage();

    await screen.findByTestId("group-stimulus");
    expect(screen.queryByText("A second, different passage.")).not.toBeInTheDocument();
    expect(getSpy.mock.calls.some(([url]) => String(url).includes("question-groups"))).toBe(false);
  });

  it("existing question types (multiple_choice) render unaffected alongside group fields absent", async () => {
    const MULTI_Q = {
      id: "q-multi", question_text: "Multi choice question", question_type: "multiple_choice", score: 1,
      options: [{ id: "o-x", option_text: "X" }, { id: "o-y", option_text: "Y" }],
    };
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(makeAttempt({ questions: [MULTI_Q], answered: answeredFor([MULTI_Q]) })),
    );
    renderPage();

    await waitFor(() => expect(screen.getByText("Multi choice question")).toBeInTheDocument());
    expect(screen.getByText("X")).toBeInTheDocument();
    expect(screen.queryByTestId("group-stimulus")).not.toBeInTheDocument();
  });
});
