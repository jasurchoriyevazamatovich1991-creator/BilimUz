/** Task 4 — scaled scores on the student result page. */
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

describe("ResultPage — Task 4 scaled scores", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(testsApi.get).mockResolvedValue({
      id: "t1", subject_id: null, grade_id: null, topic_id: null, title: "Practice", description: null,
      difficulty: "medium", duration: 60, question_count: 10, passing_score: null,
      shuffle_questions: true, shuffle_answers: true, status: "published", created_at: "", updated_at: "",
    });
  });

  it("SAT: shows each section's scaled score and the total", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE, scoring_profile: "sat", overall_scaled_score: 1150, overall_status: "scaled",
      sections: [
        sec("Reading and Writing", { score_component: "sat_reading_writing", scaled_score: 550, scaled_status: "scaled", conversion_table_version: 1 }),
        sec("Math", { score_component: "sat_math", scaled_score: 600, scaled_status: "scaled", conversion_table_version: 1 }),
      ],
    });
    renderPage();
    const overall = await screen.findByTestId("overall-scaled-score");
    expect(overall).toHaveTextContent("Umumiy ball (Total)");
    expect(overall).toHaveTextContent("1150");
    expect(screen.getAllByTestId("section-scaled-score").map((e) => e.textContent)).toEqual(["550", "600"]);
  });

  it("IELTS: pending sections and overall are explained, never shown as a number", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE, scoring_profile: "ielts", overall_scaled_score: null, overall_status: "pending",
      sections: [
        sec("Listening", { score_component: "ielts_listening", scaled_score: 6.5, scaled_status: "scaled" }),
        sec("Writing", { score_component: "ielts_writing", raw_score: 0, scaled_status: "pending_manual_grading" }),
        sec("Reading", { score_component: "ielts_reading", scaled_status: "no_conversion_table" }),
      ],
    });
    renderPage();
    const overall = await screen.findByTestId("overall-scaled-score");
    expect(overall).toHaveTextContent("Umumiy band (Overall)");
    expect(overall).toHaveTextContent("barcha bo'limlar baholangandan keyin");
    const rows = screen.getAllByTestId("section-score-row");
    expect(within(rows[0]).getByTestId("section-scaled-score")).toHaveTextContent("6.5");
    expect(rows[1]).toHaveTextContent("Baholovchi tekshiruvi kutilmoqda");
    expect(rows[2]).toHaveTextContent("Shkala ballari hali sozlanmagan");
    expect(within(rows[2]).queryByTestId("section-scaled-score")).not.toBeInTheDocument();
  });

  it("GRE: sections only, no combined score", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE, scoring_profile: "gre", overall_scaled_score: null, overall_status: "not_reported",
      sections: [sec("Verbal", { score_component: "gre_verbal", scaled_score: 158, scaled_status: "scaled" })],
    });
    renderPage();
    expect(await screen.findByTestId("overall-scaled-score")).toHaveTextContent("umumiy ball berilmaydi");
    expect(screen.getByTestId("section-scaled-score")).toHaveTextContent("158");
  });

  it("plain percentage test: no scaled UI at all (regression)", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE, sections: [sec("Mechanics", {})],
    });
    renderPage();
    expect(await screen.findByText("3 ball")).toBeInTheDocument();
    expect(screen.queryByTestId("overall-scaled-score")).not.toBeInTheDocument();
    expect(screen.queryByTestId("section-scaled-score")).not.toBeInTheDocument();
  });
});
