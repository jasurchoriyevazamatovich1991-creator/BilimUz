/** Task 9 — audit regressions on the student result page. */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ResultPage } from "./ResultPage";
import { resultsApi, type ResultDetailOut, type ResultSectionOut } from "@/api/results";
import { testsApi } from "@/api/tests";

vi.mock("@/api/results");
vi.mock("@/api/tests");
vi.mock("@/api/certificates");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/student/results/r1"]}>
        <Routes>
          <Route path="/student/results/:resultId" element={<ResultPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const BASE: ResultDetailOut = {
  id: "r1", attempt_id: "a1", user_id: "u1", test_id: "t1", score: 5, percentage: 50, is_passed: null,
  status: "final", created_at: "2026-01-01T00:00:00Z", total_questions: 10, correct_answers: 5,
  incorrect_answers: 5, unanswered: 0, time_spent_seconds: 600, questions: [], sections: [],
};
const sec = (name: string, extra: Partial<ResultSectionOut>): ResultSectionOut => ({
  id: `rs-${name}`, section_id: `s-${name}`, name, order_number: 0, raw_score: 30, scaled_score: null, ...extra,
});

describe("ResultPage — Task 9 audit", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(testsApi.get).mockResolvedValue({
      id: "t1", subject_id: null, grade_id: null, topic_id: null, title: "Practice", description: null,
      difficulty: "medium", duration: 60, question_count: 10, passing_score: null,
      shuffle_questions: true, shuffle_answers: true, status: "published", created_at: "", updated_at: "",
    });
  });

  it("an administrator's IELTS estimate table is not attributed to IELTS.org", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE, scoring_profile: "ielts", overall_status: "scaled", overall_score_lower: 6, overall_score_upper: 6.5, overall_basis: "estimate",
      sections: [
        sec("Listening", { score_component: "ielts_listening", scaled_status: "scaled", scaled_score: 6, scaled_score_lower: 6,
                            scaled_score_upper: 6, score_basis: "estimate", conversion_table_version: 2,
                            source: { title: "Markaz ichki jadvali", url: null, version: null, verified_at: null, test_form: null, test_form_label: null } }),
      ],
    });
    renderPage();
    const row = (await screen.findAllByTestId("section-score-row"))[0];
    expect(row).not.toHaveTextContent("IELTS.org");
    expect(row).toHaveTextContent("Administrator kiritgan taxminiy jadval");
    const overall = screen.getByTestId("overall-scaled-score");
    expect(within(overall).getByTestId("overall-basis")).not.toHaveTextContent("IELTS.org");
    expect(overall).toHaveTextContent("umumiy band ham taxminiy");
  });

  it("results created before provenance existed still say they are not official", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE, scoring_profile: "sat", overall_scaled_score: 1150, overall_status: "scaled",
      sections: [sec("Math", { score_component: "sat_math", scaled_score: 600, scaled_status: "scaled", conversion_table_version: 1 })],
    });
    renderPage();
    const overall = await screen.findByTestId("overall-scaled-score");
    expect(overall).toHaveTextContent("1150");
    expect(within(overall).getByTestId("practice-disclaimer")).toHaveTextContent("rasmiy SAT natijasi emas");
  });

  it("explains a paper table that was not applied to an adaptive section", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE, scoring_profile: "sat", overall_status: "pending",
      sections: [sec("Reading and Writing", { score_component: "sat_reading_writing", scaled_status: "adaptive_section_not_supported" })],
    });
    renderPage();
    const row = (await screen.findAllByTestId("section-score-row"))[0];
    expect(row).toHaveTextContent("Bo'lim adaptiv");
    expect(screen.queryByTestId("section-scaled-score")).not.toBeInTheDocument();
    expect(screen.getByTestId("practice-disclaimer")).toHaveTextContent("rasmiy SAT natijasi emas");
  });
});
