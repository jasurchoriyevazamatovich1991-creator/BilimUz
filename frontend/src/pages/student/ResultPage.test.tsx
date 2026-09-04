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
