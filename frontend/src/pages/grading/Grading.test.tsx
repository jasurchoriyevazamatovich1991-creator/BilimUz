/** Task 5 — grading queue, grading screen and rubrics page. */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { GradingQueuePage } from "./GradingQueuePage";
import { GradingItemPage } from "./GradingItemPage";
import { RubricsPage } from "@/pages/admin/RubricsPage";
import { gradingApi, type ReviewOut, type RubricOut, type SubmissionDetailOut } from "@/api/grading";
import { ApiError } from "@/api/client";

vi.mock("@/api/grading");

function renderAt(ui: React.ReactNode, path = "/admin/grading/a1/q1", route = "/admin/grading/:attemptId/:questionId") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={route} element={ui} />
          <Route path="/admin/grading" element={<div>QUEUE</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const RUBRIC: RubricOut = {
  id: "r1", score_component: "ielts_writing", version: 1, name: "Writing rubric", rounding: "half_up",
  instructions: "Score each criterion.", is_validated: false, is_current: true, created_at: "",
  criteria: [
    { key: "task", label: "Task", min: "0", max: "9", step: "1", weight: "1" },
    { key: "lexis", label: "Lexis", min: "0", max: "9", step: "1", weight: "1" },
  ],
};

const review = (over: Partial<ReviewOut>): ReviewOut => ({
  id: "rv1", status: "draft", rubric_id: "r1", rubric_version: 1, grader_id: "u1", criterion_scores: {}, criterion_total: null,
  reported_score: null, is_provisional: false, feedback: null, internal_notes: null, revision_number: 1, supersedes_id: null,
  revision_reason: null, finalized_at: null, created_at: "", updated_at: "", ...over,
});

const SUB = (over: Partial<SubmissionDetailOut> = {}): SubmissionDetailOut => ({
  attempt_id: "a1", question_id: "q1", test_title: "IELTS practice", section_name: "Writing", score_component: "ielts_writing",
  question_text: "Describe the chart", question_type: "essay", response_text: "The chart shows...", status: "pending",
  rubric: RUBRIC, reviews: [], ...over,
});

describe("GradingQueuePage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists pending items by default and filters by status", async () => {
    vi.mocked(gradingApi.listQueue).mockResolvedValue({
      items: [{ attempt_id: "a1", question_id: "q1", test_id: "t1", test_title: "IELTS practice", section_name: "Writing",
                score_component: "ielts_writing", status: "pending", finished_at: null, reported_score: null }],
      total: 1, page: 1, per_page: 20,
    });
    renderAt(<GradingQueuePage />, "/admin/grading", "/admin/grading");
    expect(await screen.findByText("IELTS practice · Writing")).toBeInTheDocument();
    expect(gradingApi.listQueue).toHaveBeenCalledWith({ status: "pending", page: 1, per_page: 20 });
    fireEvent.click(screen.getByRole("tab", { name: "Yakunlangan" }));
    await waitFor(() => expect(gradingApi.listQueue).toHaveBeenLastCalledWith({ status: "finalized", page: 1, per_page: 20 }));
  });

  it("explains a missing GRADE_SUBMISSIONS permission", async () => {
    vi.mocked(gradingApi.listQueue).mockRejectedValue(new ApiError("forbidden", null, 403));
    renderAt(<GradingQueuePage />, "/admin/grading", "/admin/grading");
    expect(await screen.findByRole("alert")).toHaveTextContent("GRADE_SUBMISSIONS");
  });
});

describe("GradingItemPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows the task, response, rubric and saves a partial draft", async () => {
    vi.mocked(gradingApi.getSubmission).mockResolvedValue(SUB());
    vi.mocked(gradingApi.saveDraft).mockResolvedValue(review({}));
    renderAt(<GradingItemPage />);
    expect(await screen.findByTestId("response-text")).toHaveTextContent("The chart shows...");
    expect(screen.getByText(/Rubrika tasdiqlanmagan/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/^Task/), { target: { value: "6" } });
    fireEvent.change(screen.getByLabelText(/Talabaga izoh/), { target: { value: "Clear" } });
    fireEvent.click(screen.getByRole("button", { name: "Qoralamani saqlash" }));
    await waitFor(() => expect(gradingApi.saveDraft).toHaveBeenCalledWith("a1", "q1", { criterion_scores: { task: "6" }, feedback: "Clear", internal_notes: null }));
  });

  it("blocks out-of-range scores and incomplete finalization client-side", async () => {
    vi.mocked(gradingApi.getSubmission).mockResolvedValue(SUB());
    renderAt(<GradingItemPage />);
    await screen.findByTestId("response-text");
    fireEvent.change(screen.getByLabelText(/^Task/), { target: { value: "10" } });
    fireEvent.click(screen.getByRole("button", { name: "Qoralamani saqlash" }));
    expect(screen.getByRole("alert")).toHaveTextContent("0–9");
    fireEvent.change(screen.getByLabelText(/^Task/), { target: { value: "6" } });
    fireEvent.click(screen.getByRole("button", { name: "Yakunlash" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Lexis: ball kiritilmagan");
    expect(gradingApi.saveDraft).not.toHaveBeenCalled();
    expect(gradingApi.finalize).not.toHaveBeenCalled();
  });

  it("finalizes after saving the visible scores", async () => {
    vi.mocked(gradingApi.getSubmission).mockResolvedValue(SUB());
    vi.mocked(gradingApi.saveDraft).mockResolvedValue(review({}));
    vi.mocked(gradingApi.finalize).mockResolvedValue(review({ status: "finalized" }));
    renderAt(<GradingItemPage />);
    await screen.findByTestId("response-text");
    fireEvent.change(screen.getByLabelText(/^Task/), { target: { value: "6" } });
    fireEvent.change(screen.getByLabelText(/^Lexis/), { target: { value: "7" } });
    fireEvent.click(screen.getByRole("button", { name: "Yakunlash" }));
    await waitFor(() => expect(gradingApi.finalize).toHaveBeenCalledWith("a1", "q1"));
    expect(gradingApi.saveDraft).toHaveBeenCalledWith("a1", "q1", { criterion_scores: { task: "6", lexis: "7" }, feedback: null, internal_notes: null });
  });

  it("a finalized grade is read-only and can only be corrected with a reason; history is shown", async () => {
    vi.mocked(gradingApi.getSubmission).mockResolvedValue(SUB({
      status: "finalized",
      reviews: [
        review({ id: "old", status: "superseded", reported_score: 5, finalized_at: "2026-10-01T00:00:00Z" }),
        review({ id: "cur", status: "finalized", reported_score: 6.5, revision_number: 2, revision_reason: "recheck", finalized_at: "2026-10-02T00:00:00Z", is_provisional: true }),
      ],
    }));
    vi.mocked(gradingApi.revise).mockResolvedValue(review({ revision_number: 3 }));
    renderAt(<GradingItemPage />);
    expect(await screen.findByTestId("final-score")).toHaveTextContent("6.5");
    expect(screen.queryByRole("button", { name: "Yakunlash" })).not.toBeInTheDocument();
    const history = screen.getByTestId("review-history");
    expect(history).toHaveTextContent("#1 · Almashtirilgan");
    expect(history).toHaveTextContent("#2 · Yakuniy");
    const start = screen.getByRole("button", { name: "Tuzatishni boshlash" });
    expect(start).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Tuzatish sababi"), { target: { value: "Coherence mis-scored" } });
    fireEvent.click(start);
    await waitFor(() => expect(gradingApi.revise).toHaveBeenCalledWith("a1", "q1", "Coherence mis-scored"));
  });

  // Task 6 — Speaking audio capture now exists, so the old "not available
  // yet" note became "the student did not send a recording".
  it("explains a missing rubric and a Speaking response without a recording", async () => {
    vi.mocked(gradingApi.getSubmission).mockResolvedValue(SUB({ rubric: null, score_component: "ielts_speaking", response_text: null }));
    renderAt(<GradingItemPage />);
    expect(await screen.findByText(/rubrika hali sozlanmagan/)).toBeInTheDocument();
    expect(screen.getByText(/audio yozuv yubormagan/)).toBeInTheDocument();
    expect(screen.getByText("Talaba javob yozmagan.")).toBeInTheDocument();
    expect(gradingApi.getAudio).not.toHaveBeenCalled();
  });

  it("Task 6 — plays the Speaking recording through the grading endpoint on request", async () => {
    vi.mocked(gradingApi.getSubmission).mockResolvedValue(SUB({ score_component: "ielts_speaking", response_text: null, has_audio: true }));
    vi.mocked(gradingApi.getAudio).mockResolvedValue(new Blob(["x"], { type: "audio/webm" }));
    const createUrl = vi.fn(() => "blob:grader-audio");
    Object.assign(URL, { createObjectURL: createUrl, revokeObjectURL: vi.fn() });
    renderAt(<GradingItemPage />);
    const btn = await screen.findByRole("button", { name: "Audio javobni tinglash" });
    expect(gradingApi.getAudio).not.toHaveBeenCalled();
    expect(screen.queryByText("Talaba javob yozmagan.")).not.toBeInTheDocument();
    fireEvent.click(btn);
    const audio = await screen.findByTestId("response-audio");
    expect(gradingApi.getAudio).toHaveBeenCalledWith("a1", "q1");
    expect(audio).toHaveAttribute("src", "blob:grader-audio");
  });

  it("Task 6 — a 403 on the recording shows a permission message", async () => {
    vi.mocked(gradingApi.getSubmission).mockResolvedValue(SUB({ score_component: "ielts_speaking", has_audio: true }));
    vi.mocked(gradingApi.getAudio).mockRejectedValue(new ApiError("forbidden", null, 403));
    renderAt(<GradingItemPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Audio javobni tinglash" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("ruxsat yo'q");
    expect(screen.getByTestId("response-text")).toHaveTextContent("The chart shows...");
  });

  it("shows a permission message on 403", async () => {
    vi.mocked(gradingApi.getSubmission).mockRejectedValue(new ApiError("forbidden", null, 403));
    renderAt(<GradingItemPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("GRADE_SUBMISSIONS");
  });
});

describe("RubricsPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists versions and publishes a new one", async () => {
    vi.mocked(gradingApi.listRubrics).mockResolvedValue([RUBRIC]);
    vi.mocked(gradingApi.createRubric).mockResolvedValue({ ...RUBRIC, version: 2 });
    renderAt(<RubricsPage />, "/admin/rubrics", "/admin/rubrics");
    expect(await screen.findByText(/v1 · Writing rubric/)).toBeInTheDocument();
    expect(screen.getByText("tasdiqlanmagan")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Nomi"), { target: { value: "Writing v2" } });
    fireEvent.change(screen.getByLabelText("Mezon 1 kaliti"), { target: { value: "task" } });
    fireEvent.change(screen.getByLabelText("Mezon 1 nomi"), { target: { value: "Task" } });
    fireEvent.click(screen.getByLabelText(/Tasdiqlangan manbaga mos/));
    fireEvent.click(screen.getByRole("button", { name: "Versiyani e'lon qilish" }));
    await waitFor(() => expect(gradingApi.createRubric).toHaveBeenCalledWith({
      score_component: "ielts_writing", name: "Writing v2", rounding: "half_up", is_validated: true, instructions: undefined,
      criteria: [{ key: "task", label: "Task", min: "0", max: "9", step: "1", weight: "1" }],
    }));
  });
});
