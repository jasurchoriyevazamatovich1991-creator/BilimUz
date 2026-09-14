import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ResultPage } from "./ResultPage";
import { resultsApi } from "@/api/results";
import { testsApi } from "@/api/tests";
import { certificatesApi } from "@/api/certificates";

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
          {/* Marker route — lets the navigation test assert the real
              destination path was reached, without depending on
              CertificateDetailPage's own internals (tested separately). */}
          <Route path="/student/certificates/:certificateId" element={<div>CERTIFICATE_DETAIL_REACHED</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const BASE_RESULT = {
  id: "r1", attempt_id: "a1", user_id: "u1", test_id: "t1",
  score: 8, percentage: 80, status: "final", created_at: "2026-01-01T00:00:00Z",
  total_questions: 10, correct_answers: 8, incorrect_answers: 2, unanswered: 0,
  time_spent_seconds: 754, questions: [],
};

describe("ResultPage — Sprint 21 certificate continuation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(testsApi.get).mockResolvedValue({
      id: "t1", subject_id: null, grade_id: null, topic_id: null, title: "Test 1", description: null,
      difficulty: "medium", duration: 30, question_count: 10, passing_score: 60,
      shuffle_questions: true, shuffle_answers: true, status: "published", created_at: "", updated_at: "",
    });
  });

  it("shows 'Sertifikat olish' when is_passed === true", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({ ...BASE_RESULT, is_passed: true });
    renderResultPage();
    await waitFor(() => expect(screen.getByText("Sertifikat olish")).toBeInTheDocument());
  });

  it("does NOT show 'Sertifikat olish' when is_passed === false", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({ ...BASE_RESULT, is_passed: false });
    renderResultPage();
    await waitFor(() => expect(screen.getByText("O'ta olmadingiz")).toBeInTheDocument());
    expect(screen.queryByText("Sertifikat olish")).not.toBeInTheDocument();
  });

  it("calls POST /certificates with the correct request body (result_id)", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({ ...BASE_RESULT, is_passed: true });
    vi.mocked(certificatesApi.issue).mockResolvedValue({
      id: "c1", user_id: "u1", result_id: "r1", template_id: null,
      certificate_number: "CERT-0001", pdf_url: null, status: "issued", created_at: "", verification_code: "VC-TEST-0001",
    });
    renderResultPage();
    await waitFor(() => expect(screen.getByText("Sertifikat olish")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Sertifikat olish"));
    await waitFor(() => expect(certificatesApi.issue).toHaveBeenCalledWith({ result_id: "r1" }));
  });

  it("navigates to the certificate detail page after successful creation", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({ ...BASE_RESULT, is_passed: true });
    vi.mocked(certificatesApi.issue).mockResolvedValue({
      id: "c1", user_id: "u1", result_id: "r1", template_id: null,
      certificate_number: "CERT-0001", pdf_url: null, status: "issued", created_at: "", verification_code: "VC-TEST-0001",
    });
    renderResultPage();
    await waitFor(() => expect(screen.getByText("Sertifikat olish")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Sertifikat olish"));
    await waitFor(() => expect(screen.getByText("CERTIFICATE_DETAIL_REACHED")).toBeInTheDocument());
  });
});

// --- Sprint 37: Result Analysis ---

describe("ResultPage — Sprint 37 Result Analysis", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(testsApi.get).mockResolvedValue({
      id: "t1", subject_id: null, grade_id: null, topic_id: null, title: "Test 1", description: null,
      difficulty: "medium", duration: 30, question_count: 10, passing_score: 60,
      shuffle_questions: true, shuffle_answers: true, status: "published", created_at: "", updated_at: "",
    });
  });

  it("renders real correct/incorrect/unanswered counts and total questions", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE_RESULT, is_passed: true, correct_answers: 7, incorrect_answers: 2, unanswered: 1, total_questions: 10,
    });
    renderResultPage();
    await waitFor(() => expect(screen.getByText("7")).toBeInTheDocument());
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("Jami savollar: 10")).toBeInTheDocument();
  });

  it("renders real time spent, formatted as minutes and seconds", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({ ...BASE_RESULT, is_passed: true, time_spent_seconds: 754 });
    renderResultPage();
    await waitFor(() => expect(screen.getByText(/12 min 34 sek/)).toBeInTheDocument());
  });

  it("does not show a time spent line when time_spent_seconds is null (never fabricates a time)", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({ ...BASE_RESULT, is_passed: true, time_spent_seconds: null });
    renderResultPage();
    await waitFor(() => expect(screen.getByText("Jami savollar: 10")).toBeInTheDocument());
    expect(screen.queryByText(/Sarflangan vaqt/)).not.toBeInTheDocument();
  });

  it("renders question review with the student's correct answer shown", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE_RESULT, is_passed: true,
      questions: [{
        question_id: "q1", question_text: "2+2 nechi?", question_type: "single_choice", explanation: "Oddiy qo'shish",
        options: [{ id: "o1", option_text: "4", is_correct: true }, { id: "o2", option_text: "5", is_correct: false }],
        selected_option: "o1", selected_options: null, is_correct: true,
      }],
    });
    renderResultPage();
    await waitFor(() => expect(screen.getByText(/2\+2 nechi\?/)).toBeInTheDocument());
    expect(screen.getByText("✓ To'g'ri")).toBeInTheDocument();
    expect(screen.getByText(/Oddiy qo'shish/)).toBeInTheDocument();
  });

  it("renders an incorrect answer with both the student's wrong pick and the correct answer distinguished", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE_RESULT, is_passed: false,
      questions: [{
        question_id: "q1", question_text: "Poytaxt qaysi?", question_type: "single_choice", explanation: null,
        options: [{ id: "o1", option_text: "Samarqand", is_correct: false }, { id: "o2", option_text: "Toshkent", is_correct: true }],
        selected_option: "o1", selected_options: null, is_correct: false,
      }],
    });
    renderResultPage();
    await waitFor(() => expect(screen.getByText("✗ Noto'g'ri")).toBeInTheDocument());
    expect(screen.getByText(/Toshkent/)).toBeInTheDocument();
    expect(screen.getByText(/Samarqand/)).toBeInTheDocument();
  });

  it("renders unanswered questions distinctly, still showing the correct answer", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE_RESULT, is_passed: false,
      questions: [{
        question_id: "q1", question_text: "Javob berilmagan savol", question_type: "single_choice", explanation: null,
        options: [{ id: "o1", option_text: "To'g'ri variant", is_correct: true }],
        selected_option: null, selected_options: null, is_correct: null,
      }],
    });
    renderResultPage();
    await waitFor(() => expect(screen.getByText("— Javob berilmagan")).toBeInTheDocument());
    expect(screen.getByText(/To'g'ri variant/)).toBeInTheDocument();
  });

  it("multiple_choice: shows all selected options and distinguishes them from correct options", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({
      ...BASE_RESULT, is_passed: true,
      questions: [{
        question_id: "q1", question_text: "Bir nechtasini tanlang", question_type: "multiple_choice", explanation: null,
        options: [
          { id: "o1", option_text: "A", is_correct: true }, { id: "o2", option_text: "B", is_correct: true },
          { id: "o3", option_text: "C", is_correct: false },
        ],
        selected_option: null, selected_options: ["o1", "o2"], is_correct: true,
      }],
    });
    renderResultPage();
    await waitFor(() => expect(screen.getByText(/Bir nechtasini tanlang/)).toBeInTheDocument());
    expect(screen.getAllByText(/to'g'ri javob/).length).toBeGreaterThanOrEqual(2);
  });

  it("shows loading state before data arrives", () => {
    vi.mocked(resultsApi.get).mockImplementation(() => new Promise(() => {}));
    renderResultPage();
    expect(screen.getByText("Yuklanmoqda...")).toBeInTheDocument();
  });

  it("shows ErrorState on API failure", async () => {
    vi.mocked(resultsApi.get).mockRejectedValue(new Error("network error"));
    renderResultPage();
    await waitFor(() => expect(screen.getByText("Natija")).toBeInTheDocument());
  });

  it("handles an empty questions array safely (no review section rendered, no crash)", async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({ ...BASE_RESULT, is_passed: true, questions: [] });
    renderResultPage();
    await waitFor(() => expect(screen.getByText("Javoblar taqsimoti")).toBeInTheDocument());
    expect(screen.queryByText("Savollarni ko'rib chiqish")).not.toBeInTheDocument();
  });
});
