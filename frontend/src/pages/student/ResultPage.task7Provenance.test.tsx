/** Task 7 — score ranges and provenance on the student result page. */
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
  id: `rs-${name}`, section_id: `s-${name}`, name, order_number: 0, raw_score: 3, scaled_score: null, ...extra,
});

const IELTS_SOURCE = {
  title: "IELTS scoring in detail (IELTS.org)", url: "https://www.ielts.org/take-a-test/your-results/ielts-scoring-in-detail",
  version: null, verified_at: "2026-10-21", test_form: null, test_form_label: null,
};
const SAT_SOURCE = {
  title: "Scoring guide — SAT Practice Test 4 (paper, nonadaptive)",
  url: "https://satsuite.collegeboard.org/media/pdf/scoring-sat-practice-test-4-digital.pdf",
  version: null, verified_at: null, test_form: "sat_practice_test_4", test_form_label: "SAT Practice Test 4 (paper, nonadaptive)",
};

const rows = () => screen.getAllByTestId("section-score-row");

describe("ResultPage — Task 7 provenance", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(testsApi.get).mockResolvedValue({
      id: "t1", subject_id: null, grade_id: null, topic_id: null, title: "Practice", description: null,
      difficulty: "medium", duration: 60, question_count: 10, passing_score: null,
      shuffle_questions: true, shuffle_answers: true, status: "published", created_at: "", updated_at: "",
    });
  });

  it("IELTS: indicative ranges are labelled estimates with the IELTS.org source", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE, scoring_profile: "ielts", overall_status: "scaled", overall_scaled_score: null,
      overall_score_lower: 7, overall_score_upper: 7.5, overall_basis: "estimate",
      sections: [
        sec("Listening", { raw_score: 25, score_component: "ielts_listening", scaled_status: "scaled", scaled_score_lower: 6, scaled_score_upper: 6.5,
                            score_basis: "estimate", source: IELTS_SOURCE }),
        sec("Writing", { raw_score: null, score_component: "ielts_writing", scaled_status: "scaled", scaled_score: 7,
                          scaled_score_lower: 7, scaled_score_upper: 7, score_basis: "rubric" }),
      ],
    });
    renderPage();
    const overall = await screen.findByTestId("overall-scaled-score");
    expect(overall).toHaveTextContent("7–7.5");
    expect(within(overall).getByTestId("overall-basis")).toHaveTextContent("Taxminiy");
    expect(overall).toHaveTextContent("Rasmiy IELTS natijasi emas");

    const listening = rows()[0];
    expect(within(listening).getByTestId("section-scaled-score")).toHaveTextContent("6–6.5");
    expect(within(listening).getByTestId("section-score-basis")).toHaveTextContent("Taxminiy");
    expect(listening).toHaveTextContent("test versiyasiga qarab farq qiladi");
    const link = within(listening).getByRole("link", { name: IELTS_SOURCE.title });
    expect(link).toHaveAttribute("href", IELTS_SOURCE.url);
    expect(listening).toHaveTextContent("tekshirilgan: 2026-10-21");

    expect(within(rows()[1]).getByTestId("section-scaled-score")).toHaveTextContent(/^7$/);
    expect(rows()[1]).toHaveTextContent("Baholovchi (rubrika)");
  });

  it("SAT: practice-test ranges name the exact form and are never called an official SAT score", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE, scoring_profile: "sat", overall_status: "scaled", overall_scaled_score: null,
      overall_score_lower: 980, overall_score_upper: 1030, overall_basis: "official_practice_test",
      sections: [
        sec("Reading and Writing", { score_component: "sat_reading_writing", scaled_status: "scaled", scaled_score_lower: 470,
                                      scaled_score_upper: 490, score_basis: "official_practice_test", source: SAT_SOURCE, conversion_table_version: 1 }),
        sec("Math", { score_component: "sat_math", scaled_status: "scaled", scaled_score: 510, scaled_score_lower: 510,
                       scaled_score_upper: 510, score_basis: "official_practice_test", source: SAT_SOURCE, conversion_table_version: 1 }),
      ],
    });
    renderPage();
    const overall = await screen.findByTestId("overall-scaled-score");
    expect(overall).toHaveTextContent("980–1030");
    expect(overall).toHaveTextContent("rasmiy SAT natijasi emas");
    expect(screen.getAllByTestId("section-scaled-score").map((e) => e.textContent)).toEqual(["470–490", "510"]);
    expect(rows()[0]).toHaveTextContent("Rasmiy amaliy test jadvali");
    expect(within(rows()[0]).getByRole("link", { name: SAT_SOURCE.test_form_label })).toHaveAttribute("href", SAT_SOURCE.url);
    expect(document.body.textContent).not.toMatch(/sertifikatlangan|rasmiy SAT natijasi\b(?! emas)/i);
  });

  it("GRE and unavailable conversions explain why there is no number", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE, scoring_profile: "gre", overall_status: "not_reported",
      sections: [
        sec("Verbal", { score_component: "gre_verbal", scaled_status: "scaled", scaled_score: 150, scaled_score_lower: 150,
                         scaled_score_upper: 150, score_basis: "estimate", source: { ...IELTS_SOURCE, title: "Internal estimate", url: null, verified_at: null } }),
        sec("Quant", { score_component: "gre_quantitative", scaled_status: "no_conversion_table" }),
      ],
    });
    renderPage();
    const overall = await screen.findByTestId("overall-scaled-score");
    expect(overall).toHaveTextContent("umumiy ball berilmaydi");
    expect(rows()[0]).toHaveTextContent("ETS ballni equating orqali hisoblaydi");
    expect(rows()[0]).toHaveTextContent("Manba: Internal estimate");
    expect(within(rows()[1]).queryByTestId("section-score-basis")).not.toBeInTheDocument();
    expect(rows()[1]).toHaveTextContent("Shkala ballari hali sozlanmagan");
  });

  it("IELTS statuses without a value explain the reason", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE, scoring_profile: "ielts", overall_status: "pending",
      sections: [
        sec("Listening", { score_component: "ielts_listening", scaled_status: "below_documented_range" }),
        sec("Reading", { score_component: "ielts_reading", scaled_status: "ielts_module_unknown" }),
        sec("Reading 2", { score_component: "ielts_reading", scaled_status: "raw_scale_mismatch" }),
      ],
    });
    renderPage();
    await screen.findByTestId("overall-scaled-score");
    expect(rows()[0]).toHaveTextContent("ko'rsatkich yo'q");
    expect(rows()[1]).toHaveTextContent("Academic/General Training");
    expect(rows()[2]).toHaveTextContent("40 ta bir ballik");
    expect(screen.queryAllByTestId("section-scaled-score")).toHaveLength(0);
  });

  it("results created before Task 7 show their score with no retro-fitted label", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE, scoring_profile: "sat", overall_scaled_score: 1150, overall_status: "scaled",
      sections: [sec("Math", { score_component: "sat_math", scaled_score: 600, scaled_status: "scaled", conversion_table_version: 1 })],
    });
    renderPage();
    const overall = await screen.findByTestId("overall-scaled-score");
    expect(overall).toHaveTextContent("1150");
    expect(within(overall).queryByTestId("overall-basis")).not.toBeInTheDocument();
    expect(screen.queryByTestId("section-score-basis")).not.toBeInTheDocument();
  });
});
