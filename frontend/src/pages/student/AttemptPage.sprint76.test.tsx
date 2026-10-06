/**
 * Sprint 76 — Generic Modular Student Exam UI (section/module-aware
 * exam execution). Same httpClient-spy style as this page's own
 * pre-existing AttemptPage.test.tsx (Sprint 67/68) — lets the REAL
 * attemptsApi/useAttempt/useModuleForAttempt/useSubmitModule code run
 * against a stubbed HTTP layer, since the exact request URLs/payloads
 * are what this sprint's contract is about.
 *
 * Covers (see Sprint 76 task's Phase 15 list): modular attempt display
 * (section/module name, module-scoped timer), module submission
 * (non-final -> next module loads; final -> navigates to ResultPage),
 * submit button disabled while pending, resume preserving the active
 * module, and that a non-modular (legacy) attempt makes no extra
 * module-related requests at all.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AttemptPage } from "./AttemptPage";
import { httpClient, type ApiEnvelope } from "@/api/client";
import type { AttemptDetailOut, ModuleForAttemptOut, SubmitModuleResultOut } from "@/api/attempts";

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
          {/* Sentinel route — confirms fireModuleSubmit()/fireSubmit() actually
              navigated here, without mocking react-router-dom itself. */}
          <Route path="/student/results/:resultId" element={<div data-testid="result-page">Result page: {location.pathname}</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const MODULE1_Q = {
  id: "q-m1", question_text: "Modul 1 savoli", question_type: "single_choice", score: 1,
  options: [{ id: "o-a", option_text: "A" }, { id: "o-b", option_text: "B" }],
};
const MODULE2_Q = {
  id: "q-m2", question_text: "Modul 2 savoli", question_type: "single_choice", score: 1,
  options: [{ id: "o-c", option_text: "C" }, { id: "o-d", option_text: "D" }],
};

// Dynamic, always-in-the-future timestamps — a hardcoded past date would
// make the Timer render "0:00"/expired immediately regardless of what
// this sprint's code does, which is not what these tests are checking.
const FAR_FUTURE = () => new Date(Date.now() + 60 * 60 * 1000).toISOString(); // whole-attempt: ~1 hour
const NEAR_FUTURE = () => new Date(Date.now() + 10 * 60 * 1000).toISOString(); // module: ~10 minutes

function makeModularAttempt(overrides: Partial<AttemptDetailOut> = {}): AttemptDetailOut {
  return {
    id: "a1",
    test_id: "t1",
    status: "in_progress",
    start_time: "2026-01-01T00:00:00Z",
    expires_at: FAR_FUTURE(), // whole-attempt timer — must be overridden by module_expires_at
    finish_time: null,
    module_id: "m1",
    module_expires_at: NEAR_FUTURE(),
    questions: [MODULE1_Q],
    answered: [{ question_id: "q-m1", is_answered: false, selected_option: null, selected_options: null, text_answer: null }],
    ...overrides,
  };
}

const MODULE1_INFO: ModuleForAttemptOut = {
  id: "m1", name: "Modul 1", order_number: 0, duration: 10,
  section_id: "s1", section_name: "Reading and Writing", section_order_number: 0,
};
const MODULE2_INFO: ModuleForAttemptOut = {
  id: "m2", name: "Modul 2", order_number: 1, duration: 20,
  section_id: "s1", section_name: "Reading and Writing", section_order_number: 0,
};

describe("AttemptPage — Sprint 76 modular exam UI", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the current section/module name (module navigator)", async () => {
    vi.spyOn(httpClient, "get").mockImplementation(async (url: string) => {
      if (url.includes("/modules/")) return envelope(MODULE1_INFO);
      return envelope(makeModularAttempt());
    });
    renderPage();

    const nav = await screen.findByTestId("module-navigator");
    await waitFor(() => expect(within(nav).getByText(/Reading and Writing/)).toBeInTheDocument());
    expect(within(nav).getByText(/Modul 1: Modul 1/)).toBeInTheDocument();
  });

  it("uses module_expires_at for the Timer, not the whole-attempt expires_at", async () => {
    vi.spyOn(httpClient, "get").mockImplementation(async (url: string) => {
      if (url.includes("/modules/")) return envelope(MODULE1_INFO);
      // module_expires_at ~10 minutes out, whole-attempt expires_at ~1 hour out —
      // the rendered countdown must reflect the shorter, module-scoped one.
      return envelope(makeModularAttempt());
    });
    renderPage();

    await waitFor(() => expect(screen.getByText("Modul 1 savoli")).toBeInTheDocument());
    // Timer renders "M:SS" (Timer.tsx's formatRemaining). module_expires_at
    // is ~10 minutes out, the whole-attempt expires_at ~60 — asserting the
    // displayed minute count is well under an hour rules out the wrong one.
    await waitFor(() => {
      const timerText = screen.getByText(/^\d+:\d{2}$/).textContent ?? "";
      const minutes = Number(timerText.split(":")[0]);
      expect(minutes).toBeLessThanOrEqual(10);
    });
  });

  it("does not request module metadata for a non-modular attempt", async () => {
    const getSpy = vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(makeModularAttempt({ module_id: null, module_expires_at: null })),
    );
    renderPage();

    await waitFor(() => expect(screen.getByText("Modul 1 savoli")).toBeInTheDocument());
    expect(getSpy.mock.calls.some(([url]) => String(url).includes("/modules/"))).toBe(false);
  });

  it("submits the module (not the whole attempt) and loads the next module on a non-final submit", async () => {
    let getAttemptCallCount = 0;
    vi.spyOn(httpClient, "get").mockImplementation(async (url: string) => {
      if (url.includes("/modules/m1")) return envelope(MODULE1_INFO);
      if (url.includes("/modules/m2")) return envelope(MODULE2_INFO);
      getAttemptCallCount += 1;
      // First GET: module 1 active. After module-submit invalidates the
      // query, the refetch must reflect the backend's routing decision.
      return envelope(getAttemptCallCount === 1 ? makeModularAttempt() : makeModularAttempt({ module_id: "m2", questions: [MODULE2_Q], answered: [{ question_id: "q-m2", is_answered: false, selected_option: null, selected_options: null, text_answer: null }] }));
    });
    const postSpy = vi.spyOn(httpClient, "post").mockResolvedValue(
      envelope<SubmitModuleResultOut>({ completed: false, next_module_id: "m2", result: null }),
    );
    renderPage();

    await waitFor(() => expect(screen.getByText("Modul 1 savoli")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Modulni yakunlash" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Modulni yakunlash" }));

    await waitFor(() => expect(postSpy).toHaveBeenCalledWith("/attempts/a1/modules/m1/submit"));
    await waitFor(() => expect(screen.getByText("Modul 2 savoli")).toBeInTheDocument());
  });

  it("navigates to the Result page when the final module completes the exam", async () => {
    vi.spyOn(httpClient, "get").mockImplementation(async (url: string) => {
      if (url.includes("/modules/")) return envelope(MODULE2_INFO);
      return envelope(makeModularAttempt({ module_id: "m2", questions: [MODULE2_Q], answered: [{ question_id: "q-m2", is_answered: false, selected_option: null, selected_options: null, text_answer: null }] }));
    });
    const finalResult = { attempt_id: "a1", score: 10, percentage: 100, is_passed: true, total_questions: 2, correct_count: 2, status: "submitted" };
    vi.spyOn(httpClient, "post").mockImplementation(async (url: string) => {
      if (url.includes("/submit")) return envelope<SubmitModuleResultOut>({ completed: true, next_module_id: null, result: finalResult });
      return envelope({ id: "r-final", attempt_id: "a1", user_id: "u1", test_id: "t1", score: 10, percentage: 100, is_passed: true, status: "final", created_at: "2026-01-01T00:00:00Z" });
    });
    renderPage();

    await waitFor(() => expect(screen.getByText("Modul 2 savoli")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Modulni yakunlash" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Modulni yakunlash" }));

    await waitFor(() => expect(screen.getByTestId("result-page")).toBeInTheDocument());
  });

  it("disables the finish button while a module submission is pending", async () => {
    vi.spyOn(httpClient, "get").mockImplementation(async (url: string) => {
      if (url.includes("/modules/")) return envelope(MODULE1_INFO);
      return envelope(makeModularAttempt());
    });
    let resolvePost: (() => void) | undefined;
    vi.spyOn(httpClient, "post").mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvePost = () => resolve(envelope<SubmitModuleResultOut>({ completed: false, next_module_id: "m2", result: null }));
        }),
    );
    renderPage();

    await waitFor(() => expect(screen.getByText("Modul 1 savoli")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Modulni yakunlash" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Modulni yakunlash" }));

    await waitFor(() => expect(screen.getByText("Yuborilmoqda...")).toBeInTheDocument());
    expect(screen.getByText("Yuborilmoqda...").closest("button")).toBeDisabled();
    resolvePost?.();
  });

  it("resume: reloading with an in-progress modular attempt shows the already-active module (no module navigator flash/reset)", async () => {
    vi.spyOn(httpClient, "get").mockImplementation(async (url: string) => {
      if (url.includes("/modules/")) return envelope(MODULE2_INFO);
      // Simulates a refresh landing directly on module 2 (already routed
      // there in a prior session) — server state is authoritative, no
      // localStorage involved.
      return envelope(makeModularAttempt({ module_id: "m2", questions: [MODULE2_Q], answered: [{ question_id: "q-m2", is_answered: false, selected_option: null, selected_options: null, text_answer: null }] }));
    });
    renderPage();

    await waitFor(() => expect(screen.getByText("Modul 2 savoli")).toBeInTheDocument());
    const nav = screen.getByTestId("module-navigator");
    expect(within(nav).getByText(/Modul 2: Modul 2/)).toBeInTheDocument();
  });
});
