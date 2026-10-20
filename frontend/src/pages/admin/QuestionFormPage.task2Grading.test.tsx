/**
 * Task 2 — short_answer automatic-grading block in QuestionFormPage.
 * Same vi.mock("@/api/questions") style as the existing form tests.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { QuestionFormPage } from "./QuestionFormPage";
import { questionsApi, type QuestionOut } from "@/api/questions";
import { useAuthStore } from "@/store/authStore";

vi.mock("@/api/questions");
vi.mock("@/api/examConfig");

const SAVED: QuestionOut = {
  id: "q1", test_id: "t1", question_text: "The meeting is in the ____.", question_type: "short_answer",
  difficulty: "medium", score: 1, explanation: null, status: "active", section_id: null, module_id: null, group_id: null,
  options: [], media: [], created_at: "", updated_at: "",
  answer_format: "numeric", accepted_answers: ["2/3", "0.667"], case_sensitive: false, numeric_tolerance: "0.001",
};

function typeInRichText(element: HTMLElement, text: string) {
  element.innerHTML = text;
  fireEvent.input(element);
}

function renderAt(path: string, route: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={route} element={<QuestionFormPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const renderCreate = () => renderAt("/admin/tests/t1/questions/new", "/admin/tests/:testId/questions/new");
const renderEdit = () => renderAt("/admin/tests/t1/questions/q1", "/admin/tests/:testId/questions/:questionId");

function chooseShortAnswer() {
  typeInRichText(screen.getByLabelText("Savol matni"), "The meeting is in the ____.");
  fireEvent.change(screen.getByLabelText("Turi"), { target: { value: "short_answer" } });
}

describe("QuestionFormPage — Task 2 short-answer grading", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Teacher" });
    vi.mocked(questionsApi.create).mockResolvedValue({ ...SAVED, answer_format: null, accepted_answers: null });
  });

  it("does not show the grading block for choice or essay questions", () => {
    renderCreate();
    expect(screen.queryByTestId("short-answer-grading")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Turi"), { target: { value: "essay" } });
    expect(screen.queryByTestId("short-answer-grading")).not.toBeInTheDocument();
  });

  it("creating a short_answer without configuration sends manual-review nulls", async () => {
    renderCreate();
    chooseShortAnswer();
    expect(screen.getByTestId("short-answer-grading")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Saqlash"));

    await waitFor(() => expect(questionsApi.create).toHaveBeenCalledOnce());
    expect(vi.mocked(questionsApi.create).mock.calls[0][0]).toMatchObject({
      question_type: "short_answer", answer_format: null, accepted_answers: null, numeric_tolerance: null,
    });
  });

  it("creates a text gap-fill with several accepted answers and case sensitivity", async () => {
    renderCreate();
    chooseShortAnswer();
    fireEvent.change(screen.getByLabelText("Javob turi"), { target: { value: "text" } });
    fireEvent.change(screen.getByLabelText("To'g'ri javob 1"), { target: { value: " library " } });
    fireEvent.click(screen.getByText("+ Javob qo'shish"));
    fireEvent.change(screen.getByLabelText("To'g'ri javob 2"), { target: { value: "the library" } });
    fireEvent.click(screen.getByLabelText("Katta-kichik harf farqlansin"));
    expect(screen.queryByLabelText("Ruxsat etilgan farq (ixtiyoriy)")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Saqlash"));

    await waitFor(() => expect(questionsApi.create).toHaveBeenCalledOnce());
    expect(vi.mocked(questionsApi.create).mock.calls[0][0]).toMatchObject({
      answer_format: "text", accepted_answers: ["library", "the library"], case_sensitive: true, numeric_tolerance: null,
    });
  });

  it("creates a numeric grid-in with a tolerance", async () => {
    renderCreate();
    chooseShortAnswer();
    fireEvent.change(screen.getByLabelText("Javob turi"), { target: { value: "numeric" } });
    fireEvent.change(screen.getByLabelText("To'g'ri javob 1"), { target: { value: "7/2" } });
    fireEvent.change(screen.getByLabelText("Ruxsat etilgan farq (ixtiyoriy)"), { target: { value: "0.01" } });
    expect(screen.queryByLabelText("Katta-kichik harf farqlansin")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Saqlash"));

    await waitFor(() => expect(questionsApi.create).toHaveBeenCalledOnce());
    expect(vi.mocked(questionsApi.create).mock.calls[0][0]).toMatchObject({
      answer_format: "numeric", accepted_answers: ["7/2"], case_sensitive: false, numeric_tolerance: "0.01",
    });
  });

  it("blocks submit with a clear message for a non-numeric accepted value", () => {
    renderCreate();
    chooseShortAnswer();
    fireEvent.change(screen.getByLabelText("Javob turi"), { target: { value: "numeric" } });
    fireEvent.change(screen.getByLabelText("To'g'ri javob 1"), { target: { value: "1,5" } });
    fireEvent.click(screen.getByText("Saqlash"));

    expect(screen.getByText(/'1,5' — son emas/)).toBeInTheDocument();
    expect(questionsApi.create).not.toHaveBeenCalled();
  });

  it("blocks submit when a format is chosen but no answer is entered", () => {
    renderCreate();
    chooseShortAnswer();
    fireEvent.change(screen.getByLabelText("Javob turi"), { target: { value: "text" } });
    fireEvent.click(screen.getByText("Saqlash"));

    expect(screen.getByText("Kamida bitta to'g'ri javob kiriting")).toBeInTheDocument();
    expect(questionsApi.create).not.toHaveBeenCalled();
  });

  it("edit mode loads the saved configuration and sends it back on save", async () => {
    vi.mocked(questionsApi.get).mockResolvedValue(SAVED);
    vi.mocked(questionsApi.update).mockResolvedValue(SAVED);
    renderEdit();

    await waitFor(() => expect(screen.getByLabelText("Javob turi")).toHaveValue("numeric"));
    expect(screen.getByLabelText("To'g'ri javob 1")).toHaveValue("2/3");
    expect(screen.getByLabelText("To'g'ri javob 2")).toHaveValue("0.667");
    expect(screen.getByLabelText("Ruxsat etilgan farq (ixtiyoriy)")).toHaveValue("0.001");

    fireEvent.click(screen.getByLabelText("To'g'ri javob 2 ni o'chirish"));
    fireEvent.click(screen.getByText("Saqlash"));

    await waitFor(() => expect(questionsApi.update).toHaveBeenCalled());
    expect(vi.mocked(questionsApi.update).mock.calls[0][1]).toMatchObject({
      answer_format: "numeric", accepted_answers: ["2/3"], numeric_tolerance: "0.001",
    });
  });

  it("edit mode can switch a question back to manual review with explicit nulls", async () => {
    vi.mocked(questionsApi.get).mockResolvedValue(SAVED);
    vi.mocked(questionsApi.update).mockResolvedValue(SAVED);
    renderEdit();

    await waitFor(() => expect(screen.getByLabelText("Javob turi")).toHaveValue("numeric"));
    fireEvent.change(screen.getByLabelText("Javob turi"), { target: { value: "" } });
    fireEvent.click(screen.getByText("Saqlash"));

    await waitFor(() => expect(questionsApi.update).toHaveBeenCalled());
    expect(vi.mocked(questionsApi.update).mock.calls[0][1]).toMatchObject({
      answer_format: null, accepted_answers: null, numeric_tolerance: null,
    });
  });
});
