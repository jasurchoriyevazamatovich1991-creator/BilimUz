/** Task 5 — finalized manual grades on the student result page. */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ResultPage } from "./ResultPage";
import { resultsApi, type ResultDetailOut, type QuestionReviewOut } from "@/api/results";
import { testsApi } from "@/api/tests";

vi.mock("@/api/results");
vi.mock("@/api/tests");
vi.mock("@/api/certificates");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/student/results/r1"]}>
        <Routes><Route path="/student/results/:resultId" element={<ResultPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const essay = (over: Partial<QuestionReviewOut>): QuestionReviewOut => ({
  question_id: "q1", question_text: "Task 2", question_type: "essay", explanation: null, options: [],
  selected_option: null, selected_options: null, is_correct: null, text_answer: "My essay", ...over,
});

const BASE: ResultDetailOut = {
  id: "r1", attempt_id: "a1", user_id: "u1", test_id: "t1", score: 0, percentage: 0, is_passed: null, status: "final",
  created_at: "", total_questions: 1, correct_answers: 0, incorrect_answers: 0, unanswered: 1, time_spent_seconds: 60,
  questions: [], sections: [], scoring_profile: "ielts", overall_status: "scaled", overall_scaled_score: 6.5, is_provisional: true,
};

describe("ResultPage — Task 5 manual grades", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(testsApi.get).mockResolvedValue({
      id: "t1", subject_id: null, grade_id: null, topic_id: null, title: "IELTS", description: null, difficulty: "medium",
      duration: 60, question_count: 1, passing_score: null, shuffle_questions: false, shuffle_answers: false, status: "published",
      created_at: "", updated_at: "",
    });
  });

  it("shows the finalized band, criteria, feedback and provisional markers", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE,
      sections: [{ id: "rs1", section_id: "s1", name: "Writing", order_number: 0, raw_score: 0, scaled_score: 6.5,
                   score_component: "ielts_writing", scaled_status: "scaled", conversion_table_version: null, is_provisional: true }],
      questions: [essay({ manual_grade: {
        reported_score: 6.5, feedback: "Develop your ideas further.", is_provisional: true, revision_number: 2, finalized_at: "",
        criteria: [{ key: "task", label: "Task response", score: "6", max: "9" }, { key: "lexis", label: "Lexical resource", score: "7", max: "9" }],
      } })],
    });
    renderPage();
    const grade = await screen.findByTestId("manual-grade");
    expect(grade).toHaveTextContent("Baho: 6.5");
    expect(grade).toHaveTextContent("(provisional)");
    expect(grade).toHaveTextContent("(tuzatilgan)");
    expect(grade).toHaveTextContent("Task response: 6 / 9");
    expect(grade).toHaveTextContent("Izoh: Develop your ideas further.");
    expect(screen.getByText("Provisional (rubrika tasdiqlanmagan)")).toBeInTheDocument();
    expect(screen.getByTestId("overall-scaled-score")).toHaveTextContent("(provisional)");
  });

  it("partially graded section and ungraded essay show no grade", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE, overall_status: "pending", overall_scaled_score: null, is_provisional: false,
      sections: [{ id: "rs1", section_id: "s1", name: "Writing", order_number: 0, raw_score: 0, scaled_score: null,
                   score_component: "ielts_writing", scaled_status: "partially_graded", conversion_table_version: null, is_provisional: false }],
      questions: [essay({ manual_grade: null })],
    });
    renderPage();
    expect(await screen.findByText(/Qisman baholangan/)).toBeInTheDocument();
    expect(screen.queryByTestId("manual-grade")).not.toBeInTheDocument();
    expect(screen.queryByText("(provisional)")).not.toBeInTheDocument();
  });
});
