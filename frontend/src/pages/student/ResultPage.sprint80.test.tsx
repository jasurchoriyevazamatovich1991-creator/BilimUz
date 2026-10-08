/**
 * Sprint 80 — Result Review RichText / LaTeX Rendering.
 * Same testing style as this page's own pre-existing ResultPage.test.tsx.
 *
 * Covers (task spec section 9): ResultPage question LaTeX renders,
 * ResultPage option LaTeX renders, group stimulus LaTeX renders in
 * Result Review, short_answer/essay text_answer behavior remains
 * correct (plain, never routed through FormulaText), and the security
 * requirements.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ResultPage } from "./ResultPage";
import { resultsApi } from "@/api/results";
import { testsApi } from "@/api/tests";

vi.mock("@/api/results");
vi.mock("@/api/tests");
vi.mock("@/api/certificates");

function renderResultPage(resultId = "r1") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/student/results/${resultId}`]}>
        <Routes>
          <Route path="/student/results/:resultId" element={<ResultPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const BASE_RESULT = {
  id: "r1", attempt_id: "a1", user_id: "u1", test_id: "t1",
  score: 8, percentage: 80, status: "final", is_passed: true, created_at: "2026-01-01T00:00:00Z",
  total_questions: 1, correct_answers: 1, incorrect_answers: 0, unanswered: 0,
  time_spent_seconds: 60, sections: [],
};

describe("ResultPage — Sprint 80 RichText/LaTeX rendering", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(testsApi.get).mockResolvedValue({
      id: "t1", subject_id: null, grade_id: null, topic_id: null, title: "Test 1", description: null,
      difficulty: "medium", duration: 30, question_count: 1, passing_score: 60,
      shuffle_questions: true, shuffle_answers: true, status: "published", created_at: "", updated_at: "",
    });
  });

  it("1. plain text question_text/option_text/explanation renders exactly as before", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE_RESULT,
      questions: [{
        question_id: "q1", question_text: "2+2 nechi?", question_type: "single_choice", explanation: "Oddiy qo'shish",
        options: [{ id: "o1", option_text: "4", is_correct: true }], selected_option: "o1", selected_options: null,
        is_correct: true, text_answer: null, group_id: null, group_title: null, stimulus_text: null,
      }],
    });
    renderResultPage();
    await waitFor(() => expect(screen.getByText(/2\+2 nechi\?/)).toBeInTheDocument());
    expect(screen.getByText(/Oddiy qo'shish/)).toBeInTheDocument();
    expect(document.querySelector(".katex")).not.toBeInTheDocument();
  });

  it("2. inline LaTeX ($...$) in question_text renders via KaTeX", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE_RESULT,
      questions: [{
        question_id: "q1", question_text: "Hisoblang: $F = ma$", question_type: "single_choice", explanation: null,
        options: [{ id: "o1", option_text: "A", is_correct: true }], selected_option: "o1", selected_options: null,
        is_correct: true, text_answer: null, group_id: null, group_title: null, stimulus_text: null,
      }],
    });
    renderResultPage();
    await waitFor(() => expect(document.querySelector(".katex")).toBeInTheDocument());
  });

  it("3. ResultPage question LaTeX renders (block $$...$$ in display mode)", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE_RESULT,
      questions: [{
        question_id: "q1", question_text: "$$E = mc^2$$", question_type: "single_choice", explanation: null,
        options: [{ id: "o1", option_text: "A", is_correct: true }], selected_option: "o1", selected_options: null,
        is_correct: true, text_answer: null, group_id: null, group_title: null, stimulus_text: null,
      }],
    });
    renderResultPage();
    await waitFor(() => expect(document.querySelector(".katex-display")).toBeInTheDocument());
  });

  it("4. ResultPage option LaTeX renders", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE_RESULT,
      questions: [{
        question_id: "q1", question_text: "Tezlikni toping", question_type: "single_choice", explanation: null,
        options: [{ id: "o1", option_text: "$v = \\frac{s}{t}$", is_correct: true }], selected_option: "o1", selected_options: null,
        is_correct: true, text_answer: null, group_id: null, group_title: null, stimulus_text: null,
      }],
    });
    renderResultPage();
    await waitFor(() => expect(document.querySelector(".katex")).toBeInTheDocument());
  });

  it("5. group stimulus_text (with LaTeX) renders in Result Review", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE_RESULT,
      questions: [{
        question_id: "q1", question_text: "Passage question", question_type: "single_choice", explanation: null,
        options: [{ id: "o1", option_text: "A", is_correct: true }], selected_option: "o1", selected_options: null,
        is_correct: true, text_answer: null,
        group_id: "grp-1", group_title: "Passage 1", stimulus_text: "Given $E = mc^2$, find...",
      }],
    });
    renderResultPage();
    const panel = await screen.findByTestId("group-stimulus");
    expect(panel).toHaveTextContent("Passage 1");
    await waitFor(() => expect(panel.querySelector(".katex")).toBeInTheDocument());
  });

  it("6. ungrouped question (group_id null) renders no stimulus panel, unaffected", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE_RESULT,
      questions: [{
        question_id: "q1", question_text: "Plain question", question_type: "single_choice", explanation: null,
        options: [{ id: "o1", option_text: "A", is_correct: true }], selected_option: "o1", selected_options: null,
        is_correct: true, text_answer: null, group_id: null, group_title: null, stimulus_text: null,
      }],
    });
    renderResultPage();
    await waitFor(() => expect(screen.getByText("Plain question")).toBeInTheDocument());
    expect(screen.queryByTestId("group-stimulus")).not.toBeInTheDocument();
  });

  it("7. short_answer text_answer renders verbatim, plain — never routed through FormulaText even if it contains $ characters", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE_RESULT, is_passed: false,
      questions: [{
        question_id: "q1", question_text: "Formulani yozing", question_type: "short_answer", explanation: null,
        options: [], selected_option: null, selected_options: null, is_correct: null,
        text_answer: "$F = ma$ deb o'ylayman", group_id: null, group_title: null, stimulus_text: null,
      }],
    });
    renderResultPage();
    await waitFor(() => expect(screen.getByText(/Javobingiz: \$F = ma\$ deb o'ylayman/)).toBeInTheDocument());
    expect(document.querySelector(".katex")).not.toBeInTheDocument();
  });

  it("8. essay text_answer renders verbatim, plain — never routed through FormulaText", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE_RESULT, is_passed: false,
      questions: [{
        question_id: "q1", question_text: "Insho", question_type: "essay", explanation: null,
        options: [], selected_option: null, selected_options: null, is_correct: null,
        text_answer: "Essay containing $ dollar sign literally", group_id: null, group_title: null, stimulus_text: null,
      }],
    });
    renderResultPage();
    await waitFor(() => expect(screen.getByText(/Javobingiz: Essay containing \$ dollar sign literally/)).toBeInTheDocument());
    expect(document.querySelector(".katex")).not.toBeInTheDocument();
  });

  // --- Security ---

  it("9. a <script> tag embedded in question_text is never executed", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE_RESULT,
      questions: [{
        question_id: "q1", question_text: "<script>window.__resultXss = true</script>Xavfsizlik matni", question_type: "single_choice", explanation: null,
        options: [{ id: "o1", option_text: "A", is_correct: true }], selected_option: "o1", selected_options: null,
        is_correct: true, text_answer: null, group_id: null, group_title: null, stimulus_text: null,
      }],
    });
    renderResultPage();
    // A <script> tag inserted via dangerouslySetInnerHTML is parsed into
    // the DOM (browser/jsdom-spec behavior) but is never EXECUTED that
    // way — what matters is that it never runs.
    await waitFor(() => expect(screen.getByText(/Xavfsizlik matni/)).toBeInTheDocument());
    expect((window as unknown as { __resultXss?: boolean }).__resultXss).toBeUndefined();
  });

  it("10. an event-handler attribute embedded in explanation does not execute on render", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE_RESULT,
      questions: [{
        question_id: "q1", question_text: "Savol", question_type: "single_choice",
        explanation: '<img src="x" onerror="window.__resultXss2 = true" />Izoh matni',
        options: [{ id: "o1", option_text: "A", is_correct: true }], selected_option: "o1", selected_options: null,
        is_correct: true, text_answer: null, group_id: null, group_title: null, stimulus_text: null,
      }],
    });
    renderResultPage();
    await waitFor(() => expect(screen.getByText(/Izoh matni/)).toBeInTheDocument());
    expect((window as unknown as { __resultXss2?: boolean }).__resultXss2).toBeUndefined();
  });

  // --- Regression: existing Sprint 37/70/73 behavior unaffected ---

  it("11. multiple_choice option highlighting (selected vs correct) still works alongside FormulaText rendering", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE_RESULT, is_passed: true,
      questions: [{
        question_id: "q1", question_text: "Bir nechtasini tanlang", question_type: "multiple_choice", explanation: null,
        options: [
          { id: "o1", option_text: "A", is_correct: true }, { id: "o2", option_text: "B", is_correct: true },
          { id: "o3", option_text: "C", is_correct: false },
        ],
        selected_option: null, selected_options: ["o1", "o2"], is_correct: true, text_answer: null,
        group_id: null, group_title: null, stimulus_text: null,
      }],
    });
    renderResultPage();
    await waitFor(() => expect(screen.getByText(/Bir nechtasini tanlang/)).toBeInTheDocument());
    expect(screen.getAllByText(/to'g'ri javob/).length).toBeGreaterThanOrEqual(2);
  });
});
