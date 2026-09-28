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
      { question_id: "q-single", is_answered: false, selected_option: null, selected_options: null },
      { question_id: "q-multi", is_answered: false, selected_option: null, selected_options: null },
      { question_id: "q-tf", is_answered: false, selected_option: null, selected_options: null },
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
            { question_id: "q-single", is_answered: false, selected_option: null, selected_options: null },
            { question_id: "q-multi", is_answered: true, selected_option: null, selected_options: ["o-red", "o-yellow"] },
            { question_id: "q-tf", is_answered: false, selected_option: null, selected_options: null },
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
            { question_id: "q-single", is_answered: false, selected_option: null, selected_options: null },
            { question_id: "q-multi", is_answered: true, selected_option: null, selected_options: ["o-blue"] },
            { question_id: "q-tf", is_answered: false, selected_option: null, selected_options: null },
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
