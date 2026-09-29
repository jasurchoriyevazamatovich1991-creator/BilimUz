/**
 * Sprint 67 (C2) — AttemptPage multiple_choice frontend support.
 *
 * Unlike TestDetailPage.test.tsx's `vi.mock("@/api/attempts")` (which
 * replaces every exported function with a bare mock, losing the real
 * request-body-building logic inside attemptsApi.saveAnswer()), these
 * tests spy on the underlying `httpClient` methods instead and let the
 * REAL attemptsApi/useAttempt code run on top of them. This is
 * deliberate: Sprint 65's audit finding and this sprint's fix are both
 * about the exact request payload sent over the wire, so the tests
 * verify that literal payload, not just that some mocked function was
 * called with some object.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within, fireEvent } from "@testing-library/react";
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

const SINGLE_CHOICE_Q = {
  id: "q-single",
  question_text: "Poytaxt qaysi shahar?",
  question_type: "single_choice",
  score: 1,
  options: [
    { id: "o-tashkent", option_text: "Toshkent" },
    { id: "o-samarkand", option_text: "Samarqand" },
  ],
};

const TRUE_FALSE_Q = {
  id: "q-tf",
  question_text: "Yer dumaloqmi?",
  question_type: "true_false",
  score: 1,
  options: [
    { id: "o-true", option_text: "To'g'ri" },
    { id: "o-false", option_text: "Noto'g'ri" },
  ],
};

const MULTIPLE_CHOICE_Q = {
  id: "q-multi",
  question_text: "Qaysi ranglar issiq ranglar?",
  question_type: "multiple_choice",
  score: 1,
  options: [
    { id: "o-red", option_text: "Qizil" },
    { id: "o-yellow", option_text: "Sariq" },
    { id: "o-blue", option_text: "Ko'k" },
  ],
};

function makeAttempt(overrides: Partial<AttemptDetailOut> = {}): AttemptDetailOut {
  return {
    id: "a1",
    test_id: "t1",
    status: "in_progress",
    start_time: "2026-01-01T00:00:00Z",
    expires_at: null, // no Timer — keeps these tests focused on option rendering/saving
    finish_time: null,
    questions: [SINGLE_CHOICE_Q, MULTIPLE_CHOICE_Q, TRUE_FALSE_Q],
    answered: [
      { question_id: "q-single", is_answered: false, selected_option: null, selected_options: null, text_answer: null },
      { question_id: "q-multi", is_answered: false, selected_option: null, selected_options: null, text_answer: null },
      { question_id: "q-tf", is_answered: false, selected_option: null, selected_options: null, text_answer: null },
    ],
    ...overrides,
  };
}

describe("AttemptPage — Sprint 67 (C2) multiple_choice support", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  // --- TEST 1/2/3: rendering per question_type -----------------------

  it("TEST 1/2: single_choice question renders radio inputs, not checkboxes", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(envelope(makeAttempt()));
    renderPage();

    await waitFor(() => expect(screen.getByText("Toshkent")).toBeInTheDocument());
    const region = screen.getByText("Toshkent").closest("label")!;
    expect(within(region).getByRole("radio")).toBeInTheDocument();
    expect(within(region).queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("TEST 3: true_false question renders radio inputs, not checkboxes", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(envelope(makeAttempt()));
    renderPage();

    await waitFor(() => expect(screen.getByText("Toshkent")).toBeInTheDocument());
    // Navigate: single_choice (index 0) -> multiple_choice (index 1) -> true_false (index 2)
    fireEvent.click(screen.getByText("Keyingi"));
    fireEvent.click(screen.getByText("Keyingi"));
    await waitFor(() => expect(screen.getByText("To'g'ri")).toBeInTheDocument());

    const region = screen.getByText("To'g'ri").closest("label")!;
    expect(within(region).getByRole("radio")).toBeInTheDocument();
    expect(within(region).queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("TEST 1: multiple_choice question renders checkbox inputs, not radios", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(envelope(makeAttempt()));
    renderPage();

    await waitFor(() => expect(screen.getByText("Toshkent")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Keyingi")); // -> multiple_choice
    await waitFor(() => expect(screen.getByText("Qizil")).toBeInTheDocument());

    const region = screen.getByText("Qizil").closest("label")!;
    expect(within(region).getByRole("checkbox")).toBeInTheDocument();
    expect(within(region).queryByRole("radio")).not.toBeInTheDocument();
  });

  // --- TEST 4/5: checkbox toggle accumulates/removes ------------------

  it("TEST 4: clicking multiple_choice options accumulates selections (A, then B -> [A, B])", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(envelope(makeAttempt()));
    const patchSpy = vi.spyOn(httpClient, "patch").mockResolvedValue(envelope(null));
    renderPage();

    await waitFor(() => expect(screen.getByText("Toshkent")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Keyingi"));
    await waitFor(() => expect(screen.getByText("Qizil")).toBeInTheDocument());

    fireEvent.click(within(screen.getByText("Qizil").closest("label")!).getByRole("checkbox"));
    await waitFor(() =>
      expect(patchSpy).toHaveBeenLastCalledWith("/attempts/a1/answer", { question_id: "q-multi", selected_options: ["o-red"] }),
    );

    fireEvent.click(within(screen.getByText("Sariq").closest("label")!).getByRole("checkbox"));
    await waitFor(() =>
      expect(patchSpy).toHaveBeenLastCalledWith("/attempts/a1/answer", { question_id: "q-multi", selected_options: ["o-red", "o-yellow"] }),
    );
  });

  it("TEST 5: clicking an already-selected multiple_choice option removes it ([A, B] -> click A -> [B])", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(
        makeAttempt({
          answered: [
            { question_id: "q-single", is_answered: false, selected_option: null, selected_options: null, text_answer: null },
            { question_id: "q-multi", is_answered: true, selected_option: null, selected_options: ["o-red", "o-yellow"], text_answer: null },
            { question_id: "q-tf", is_answered: false, selected_option: null, selected_options: null, text_answer: null },
          ],
        }),
      ),
    );
    const patchSpy = vi.spyOn(httpClient, "patch").mockResolvedValue(envelope(null));
    renderPage();

    await waitFor(() => expect(screen.getByText("Toshkent")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Keyingi"));
    await waitFor(() => expect(screen.getByText("Qizil")).toBeInTheDocument());

    // TEST 10 (rendered-as-checked-on-load) is exercised here too:
    expect(within(screen.getByText("Qizil").closest("label")!).getByRole("checkbox")).toBeChecked();
    expect(within(screen.getByText("Sariq").closest("label")!).getByRole("checkbox")).toBeChecked();
    expect(within(screen.getByText("Ko'k").closest("label")!).getByRole("checkbox")).not.toBeChecked();

    fireEvent.click(within(screen.getByText("Qizil").closest("label")!).getByRole("checkbox"));
    await waitFor(() =>
      expect(patchSpy).toHaveBeenLastCalledWith("/attempts/a1/answer", { question_id: "q-multi", selected_options: ["o-yellow"] }),
    );
  });

  // --- TEST 6/7/8: exact wire payload per question_type ---------------

  it("TEST 6: multiple_choice submission sends {question_id, selected_options} — never a selected_option field", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(envelope(makeAttempt()));
    const patchSpy = vi.spyOn(httpClient, "patch").mockResolvedValue(envelope(null));
    renderPage();

    await waitFor(() => expect(screen.getByText("Toshkent")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Keyingi"));
    await waitFor(() => expect(screen.getByText("Qizil")).toBeInTheDocument());
    fireEvent.click(within(screen.getByText("Qizil").closest("label")!).getByRole("checkbox"));

    await waitFor(() => expect(patchSpy).toHaveBeenCalled());
    const body = patchSpy.mock.calls[0][1] as Record<string, unknown>;
    expect(body).toEqual({ question_id: "q-multi", selected_options: ["o-red"] });
    expect(body).not.toHaveProperty("selected_option");
  });

  it("TEST 7: single_choice submission still sends {question_id, selected_option}", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(envelope(makeAttempt()));
    const patchSpy = vi.spyOn(httpClient, "patch").mockResolvedValue(envelope(null));
    renderPage();

    await waitFor(() => expect(screen.getByText("Toshkent")).toBeInTheDocument());
    fireEvent.click(within(screen.getByText("Toshkent").closest("label")!).getByRole("radio"));

    await waitFor(() => expect(patchSpy).toHaveBeenCalled());
    expect(patchSpy).toHaveBeenLastCalledWith("/attempts/a1/answer", { question_id: "q-single", selected_option: "o-tashkent" });
  });

  it("TEST 8: true_false submission still sends {question_id, selected_option}", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(envelope(makeAttempt()));
    const patchSpy = vi.spyOn(httpClient, "patch").mockResolvedValue(envelope(null));
    renderPage();

    await waitFor(() => expect(screen.getByText("Toshkent")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Keyingi"));
    fireEvent.click(screen.getByText("Keyingi"));
    await waitFor(() => expect(screen.getByText("To'g'ri")).toBeInTheDocument());
    fireEvent.click(within(screen.getByText("To'g'ri").closest("label")!).getByRole("radio"));

    await waitFor(() => expect(patchSpy).toHaveBeenCalled());
    expect(patchSpy).toHaveBeenLastCalledWith("/attempts/a1/answer", { question_id: "q-tf", selected_option: "o-true" });
  });

  // --- TEST 9: selections survive navigating away and back ------------

  it("TEST 9: multiple_choice selections survive navigating to another question and back", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(envelope(makeAttempt()));
    vi.spyOn(httpClient, "patch").mockResolvedValue(envelope(null));
    renderPage();

    await waitFor(() => expect(screen.getByText("Toshkent")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Keyingi"));
    await waitFor(() => expect(screen.getByText("Qizil")).toBeInTheDocument());

    fireEvent.click(within(screen.getByText("Qizil").closest("label")!).getByRole("checkbox"));
    await waitFor(() => expect(within(screen.getByText("Qizil").closest("label")!).getByRole("checkbox")).toBeChecked());
    fireEvent.click(within(screen.getByText("Sariq").closest("label")!).getByRole("checkbox"));
    await waitFor(() => expect(within(screen.getByText("Sariq").closest("label")!).getByRole("checkbox")).toBeChecked());

    // Navigate away (true_false) and back (multiple_choice) — no
    // separate/temporary state, only the existing attempt-detail cache.
    fireEvent.click(screen.getByText("Keyingi"));
    await waitFor(() => expect(screen.getByText("To'g'ri")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Oldingi"));
    await waitFor(() => expect(screen.getByText("Qizil")).toBeInTheDocument());

    expect(within(screen.getByText("Qizil").closest("label")!).getByRole("checkbox")).toBeChecked();
    expect(within(screen.getByText("Sariq").closest("label")!).getByRole("checkbox")).toBeChecked();
    expect(within(screen.getByText("Ko'k").closest("label")!).getByRole("checkbox")).not.toBeChecked();
  });

  // --- TEST 10: existing selected_options rendered as checked on load -
  // (also exercised inline above in TEST 5's setup; this is the
  // dedicated, isolated test for it)

  it("TEST 10: an attempt loaded with existing selected_options renders them as checked", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(
        makeAttempt({
          answered: [
            { question_id: "q-single", is_answered: false, selected_option: null, selected_options: null, text_answer: null },
            { question_id: "q-multi", is_answered: true, selected_option: null, selected_options: ["o-blue"], text_answer: null },
            { question_id: "q-tf", is_answered: false, selected_option: null, selected_options: null, text_answer: null },
          ],
        }),
      ),
    );
    renderPage();

    await waitFor(() => expect(screen.getByText("Toshkent")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Keyingi"));
    await waitFor(() => expect(screen.getByText("Ko'k")).toBeInTheDocument());

    expect(within(screen.getByText("Ko'k").closest("label")!).getByRole("checkbox")).toBeChecked();
    expect(within(screen.getByText("Qizil").closest("label")!).getByRole("checkbox")).not.toBeChecked();
    expect(within(screen.getByText("Sariq").closest("label")!).getByRole("checkbox")).not.toBeChecked();
  });

  // --- An empty multiple_choice selection is not "answered" -----------

  it("an unanswered multiple_choice question is not counted as answered (empty selection)", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(envelope(makeAttempt()));
    renderPage();

    await waitFor(() => expect(screen.getByText("Toshkent")).toBeInTheDocument());
    // 0 answered out of 3 -> confirm dialog copy reflects all 3 unanswered.
    fireEvent.click(screen.getByText("Yakunlash"));
    await waitFor(() => expect(screen.getByText(/3 ta savolga javob berilmagan/)).toBeInTheDocument());
  });
});

// =====================================================================
// Sprint 68 — short_answer / essay frontend completion
// =====================================================================

const SHORT_ANSWER_Q = {
  id: "q-short",
  question_text: "Toshkent qachon poytaxt bo'lgan?",
  question_type: "short_answer",
  score: 1,
  options: [],
};

const ESSAY_Q = {
  id: "q-essay",
  question_text: "O'zbekiston tarixi haqida qisqacha yozing.",
  question_type: "essay",
  score: 5,
  options: [],
};

function makeTextAttempt(overrides: Partial<AttemptDetailOut> = {}): AttemptDetailOut {
  return {
    id: "a1",
    test_id: "t1",
    status: "in_progress",
    start_time: "2026-01-01T00:00:00Z",
    expires_at: null,
    finish_time: null,
    questions: [SHORT_ANSWER_Q, ESSAY_Q],
    answered: [
      { question_id: "q-short", is_answered: false, selected_option: null, selected_options: null, text_answer: null },
      { question_id: "q-essay", is_answered: false, selected_option: null, selected_options: null, text_answer: null },
    ],
    ...overrides,
  };
}

describe("AttemptPage — Sprint 68 short_answer/essay support", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  // --- TEST 1/2: rendering ---------------------------------------------

  it("TEST 1: short_answer renders a text input", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(envelope(makeTextAttempt()));
    renderPage();

    await waitFor(() => expect(screen.getByText(/Toshkent qachon/)).toBeInTheDocument());
    expect(screen.getByPlaceholderText("Javobingizni shu yerga yozing...").tagName).toBe("INPUT");
  });

  it("TEST 2: essay renders a textarea", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(envelope(makeTextAttempt()));
    renderPage();

    await waitFor(() => expect(screen.getByText(/Toshkent qachon/)).toBeInTheDocument());
    fireEvent.click(screen.getByText("Keyingi"));
    await waitFor(() => expect(screen.getByText(/O'zbekiston tarixi/)).toBeInTheDocument());
    expect(screen.getByPlaceholderText("Javobingizni shu yerga yozing...").tagName).toBe("TEXTAREA");
  });

  // --- TEST 3/4: exact wire payload -------------------------------------

  it("TEST 3: short_answer typing sends {question_id, text_answer} and never selected_option(s)", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(envelope(makeTextAttempt()));
    const patchSpy = vi.spyOn(httpClient, "patch").mockResolvedValue(envelope(null));
    renderPage();

    await waitFor(() => expect(screen.getByText(/Toshkent qachon/)).toBeInTheDocument());
    const field = screen.getByPlaceholderText("Javobingizni shu yerga yozing...");
    fireEvent.change(field, { target: { value: "1930-yillarda" } });
    fireEvent.blur(field);

    await waitFor(() => expect(patchSpy).toHaveBeenCalled());
    const body = patchSpy.mock.calls[0][1] as Record<string, unknown>;
    expect(body).toEqual({ question_id: "q-short", text_answer: "1930-yillarda" });
    expect(body).not.toHaveProperty("selected_option");
    expect(body).not.toHaveProperty("selected_options");
  });

  it("TEST 4: essay typing sends text_answer with the same contract", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(envelope(makeTextAttempt()));
    const patchSpy = vi.spyOn(httpClient, "patch").mockResolvedValue(envelope(null));
    renderPage();

    await waitFor(() => expect(screen.getByText(/Toshkent qachon/)).toBeInTheDocument());
    fireEvent.click(screen.getByText("Keyingi"));
    await waitFor(() => expect(screen.getByText(/O'zbekiston tarixi/)).toBeInTheDocument());

    const field = screen.getByPlaceholderText("Javobingizni shu yerga yozing...");
    fireEvent.change(field, { target: { value: "Uzoq va boy tarixga ega." } });
    fireEvent.blur(field);

    await waitFor(() => expect(patchSpy).toHaveBeenCalled());
    const body = patchSpy.mock.calls[0][1] as Record<string, unknown>;
    expect(body).toEqual({ question_id: "q-essay", text_answer: "Uzoq va boy tarixga ega." });
    expect(body).not.toHaveProperty("selected_option");
    expect(body).not.toHaveProperty("selected_options");
  });

  // --- TEST 5/6: resume from an existing text_answer --------------------

  it("TEST 5: short_answer with an existing text_answer resumes correctly", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(
        makeTextAttempt({
          answered: [
            { question_id: "q-short", is_answered: true, selected_option: null, selected_options: null, text_answer: "1930-yillarda" },
            { question_id: "q-essay", is_answered: false, selected_option: null, selected_options: null, text_answer: null },
          ],
        }),
      ),
    );
    renderPage();

    await waitFor(() => expect(screen.getByText(/Toshkent qachon/)).toBeInTheDocument());
    expect(screen.getByPlaceholderText("Javobingizni shu yerga yozing...")).toHaveValue("1930-yillarda");
  });

  it("TEST 6: essay with an existing text_answer resumes correctly", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(
        makeTextAttempt({
          answered: [
            { question_id: "q-short", is_answered: false, selected_option: null, selected_options: null, text_answer: null },
            { question_id: "q-essay", is_answered: true, selected_option: null, selected_options: null, text_answer: "Uzoq tarix." },
          ],
        }),
      ),
    );
    renderPage();

    await waitFor(() => expect(screen.getByText(/Toshkent qachon/)).toBeInTheDocument());
    fireEvent.click(screen.getByText("Keyingi"));
    await waitFor(() => expect(screen.getByText(/O'zbekiston tarixi/)).toBeInTheDocument());
    expect(screen.getByPlaceholderText("Javobingizni shu yerga yozing...")).toHaveValue("Uzoq tarix.");
  });

  // --- TEST 7/8: non-empty text is answered ------------------------------

  it("TEST 7: non-empty short_answer is treated as answered", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(envelope(makeTextAttempt()));
    vi.spyOn(httpClient, "patch").mockResolvedValue(envelope(null));
    renderPage();

    await waitFor(() => expect(screen.getByText(/Toshkent qachon/)).toBeInTheDocument());
    const field = screen.getByPlaceholderText("Javobingizni shu yerga yozing...");
    fireEvent.change(field, { target: { value: "1930" } });
    fireEvent.blur(field);

    fireEvent.click(screen.getByText("Yakunlash"));
    // 1 answered out of 2 -> only 1 remaining unanswered (essay).
    await waitFor(() => expect(screen.getByText(/1 ta savolga javob berilmagan/)).toBeInTheDocument());
  });

  it("TEST 8: non-empty essay is treated as answered", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(envelope(makeTextAttempt()));
    vi.spyOn(httpClient, "patch").mockResolvedValue(envelope(null));
    renderPage();

    await waitFor(() => expect(screen.getByText(/Toshkent qachon/)).toBeInTheDocument());
    fireEvent.click(screen.getByText("Keyingi"));
    await waitFor(() => expect(screen.getByText(/O'zbekiston tarixi/)).toBeInTheDocument());
    const field = screen.getByPlaceholderText("Javobingizni shu yerga yozing...");
    fireEvent.change(field, { target: { value: "Javob matni" } });
    fireEvent.blur(field);

    fireEvent.click(screen.getByText("Yakunlash"));
    await waitFor(() => expect(screen.getByText(/1 ta savolga javob berilmagan/)).toBeInTheDocument());
  });

  // --- TEST 9/10: empty text is unanswered --------------------------------

  it("TEST 9: empty short_answer is treated as unanswered", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(envelope(makeTextAttempt()));
    renderPage();

    await waitFor(() => expect(screen.getByText(/Toshkent qachon/)).toBeInTheDocument());
    fireEvent.click(screen.getByText("Yakunlash"));
    await waitFor(() => expect(screen.getByText(/2 ta savolga javob berilmagan/)).toBeInTheDocument());
  });

  it("TEST 10: empty essay is treated as unanswered", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope(
        makeTextAttempt({
          answered: [
            { question_id: "q-short", is_answered: false, selected_option: null, selected_options: null, text_answer: null },
            // Backend row exists (e.g. student typed then cleared it) but
            // text is empty — must still count as unanswered client-side.
            { question_id: "q-essay", is_answered: true, selected_option: null, selected_options: null, text_answer: "" },
          ],
        }),
      ),
    );
    renderPage();

    await waitFor(() => expect(screen.getByText(/Toshkent qachon/)).toBeInTheDocument());
    fireEvent.click(screen.getByText("Yakunlash"));
    await waitFor(() => expect(screen.getByText(/2 ta savolga javob berilmagan/)).toBeInTheDocument());
  });

  // --- TEST 11/12: navigation preserves the text --------------------------

  it("TEST 11: navigation preserves short_answer text", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(envelope(makeTextAttempt()));
    vi.spyOn(httpClient, "patch").mockResolvedValue(envelope(null));
    renderPage();

    await waitFor(() => expect(screen.getByText(/Toshkent qachon/)).toBeInTheDocument());
    const field = screen.getByPlaceholderText("Javobingizni shu yerga yozing...");
    fireEvent.change(field, { target: { value: "1930-yillarda" } });
    fireEvent.blur(field);
    await waitFor(() => expect(httpClient.patch).toHaveBeenCalled());

    fireEvent.click(screen.getByText("Keyingi"));
    await waitFor(() => expect(screen.getByText(/O'zbekiston tarixi/)).toBeInTheDocument());
    fireEvent.click(screen.getByText("Oldingi"));
    await waitFor(() => expect(screen.getByText(/Toshkent qachon/)).toBeInTheDocument());

    expect(screen.getByPlaceholderText("Javobingizni shu yerga yozing...")).toHaveValue("1930-yillarda");
  });

  it("TEST 12: navigation preserves essay text", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(envelope(makeTextAttempt()));
    vi.spyOn(httpClient, "patch").mockResolvedValue(envelope(null));
    renderPage();

    await waitFor(() => expect(screen.getByText(/Toshkent qachon/)).toBeInTheDocument());
    fireEvent.click(screen.getByText("Keyingi"));
    await waitFor(() => expect(screen.getByText(/O'zbekiston tarixi/)).toBeInTheDocument());

    const field = screen.getByPlaceholderText("Javobingizni shu yerga yozing...");
    fireEvent.change(field, { target: { value: "Uzoq tarix." } });
    fireEvent.blur(field);
    await waitFor(() => expect(httpClient.patch).toHaveBeenCalled());

    fireEvent.click(screen.getByText("Oldingi"));
    await waitFor(() => expect(screen.getByText(/Toshkent qachon/)).toBeInTheDocument());
    fireEvent.click(screen.getByText("Keyingi"));
    await waitFor(() => expect(screen.getByText(/O'zbekiston tarixi/)).toBeInTheDocument());

    expect(screen.getByPlaceholderText("Javobingizni shu yerga yozing...")).toHaveValue("Uzoq tarix.");
  });

  // --- TEST 13/14: existing question types unaffected ---------------------
  // (multiple_choice checkbox and single_choice/true_false radio tests
  // already exist above in the Sprint 67 describe block and continue to
  // run in this same file/suite — TEST 4, TEST 6, TEST 7, TEST 8 there
  // are the direct proof these were not regressed by this sprint's
  // changes to answeredMap/useSaveAnswer/AttemptPage. Two focused
  // re-checks here, scoped to a mixed attempt that also contains a
  // short_answer question, to prove the new branch doesn't leak into
  // the other rendering paths.)

  it("TEST 13: multiple_choice checkbox rendering/behavior is unaffected by short_answer support", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope({
        id: "a1",
        test_id: "t1",
        status: "in_progress",
        start_time: "2026-01-01T00:00:00Z",
        expires_at: null,
        finish_time: null,
        questions: [MULTIPLE_CHOICE_Q, SHORT_ANSWER_Q],
        answered: [
          { question_id: "q-multi", is_answered: false, selected_option: null, selected_options: null, text_answer: null },
          { question_id: "q-short", is_answered: false, selected_option: null, selected_options: null, text_answer: null },
        ],
      }),
    );
    const patchSpy = vi.spyOn(httpClient, "patch").mockResolvedValue(envelope(null));
    renderPage();

    await waitFor(() => expect(screen.getByText("Qizil")).toBeInTheDocument());
    const region = screen.getByText("Qizil").closest("label")!;
    expect(within(region).getByRole("checkbox")).toBeInTheDocument();
    fireEvent.click(within(region).getByRole("checkbox"));
    await waitFor(() =>
      expect(patchSpy).toHaveBeenLastCalledWith("/attempts/a1/answer", { question_id: "q-multi", selected_options: ["o-red"] }),
    );
  });

  it("TEST 14: single_choice/true_false radio rendering is unaffected by short_answer support", async () => {
    vi.spyOn(httpClient, "get").mockResolvedValue(
      envelope({
        id: "a1",
        test_id: "t1",
        status: "in_progress",
        start_time: "2026-01-01T00:00:00Z",
        expires_at: null,
        finish_time: null,
        questions: [SINGLE_CHOICE_Q, SHORT_ANSWER_Q],
        answered: [
          { question_id: "q-single", is_answered: false, selected_option: null, selected_options: null, text_answer: null },
          { question_id: "q-short", is_answered: false, selected_option: null, selected_options: null, text_answer: null },
        ],
      }),
    );
    const patchSpy = vi.spyOn(httpClient, "patch").mockResolvedValue(envelope(null));
    renderPage();

    await waitFor(() => expect(screen.getByText("Toshkent")).toBeInTheDocument());
    fireEvent.click(within(screen.getByText("Toshkent").closest("label")!).getByRole("radio"));
    await waitFor(() =>
      expect(patchSpy).toHaveBeenLastCalledWith("/attempts/a1/answer", { question_id: "q-single", selected_option: "o-tashkent" }),
    );
  });
});
