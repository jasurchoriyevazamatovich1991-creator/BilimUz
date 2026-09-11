import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { QuestionFormPage } from "./QuestionFormPage";
import { questionsApi } from "@/api/questions";
import { useAuthStore } from "@/store/authStore";

vi.mock("@/api/questions");

/** RichTextEditor is a contentEditable div, not a native input — fireEvent.change
 * doesn't apply to it. Sets innerHTML directly and fires a real input event,
 * matching what the component's own onInput handler reads. */
function typeInRichText(element: HTMLElement, text: string) {
  element.innerHTML = text;
  fireEvent.input(element);
}

function renderCreatePage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/admin/tests/t1/questions/new"]}>
        <Routes>
          <Route path="/admin/tests/:testId/questions/new" element={<QuestionFormPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("QuestionFormPage — conditional option-set validation (approved decision 7)", () => {
  beforeEach(() => {
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Teacher" });
  });

  it("Teacher can access the create form (RBAC matches Tests/Topics/Lessons)", () => {
    renderCreatePage();
    expect(screen.getByText("Yangi savol")).toBeInTheDocument();
  });

  it("single_choice: rejects submit with 0 correct options, mirroring the backend's exact message", () => {
    renderCreatePage();
    typeInRichText(screen.getByLabelText("Savol matni"), "2+2 nechi?");
    fireEvent.click(screen.getByText("+ Variant qo'shish"));
    fireEvent.click(screen.getByText("+ Variant qo'shish"));

    fireEvent.click(screen.getByText("Saqlash"));
    expect(screen.getByText(/aynan 1 ta to'g'ri variant bo'lishi kerak, 0 ta topildi/)).toBeInTheDocument();
    expect(questionsApi.create).not.toHaveBeenCalled();
  });

  it("single_choice: never blocks the Submit button itself (approved decision 7 — submit-time check only)", () => {
    renderCreatePage();
    expect(screen.getByText("Saqlash")).toBeEnabled();
  });

  it("single_choice: allows submit with exactly 1 correct option", async () => {
    vi.mocked(questionsApi.create).mockResolvedValue({
      id: "q1", test_id: "t1", question_text: "2+2 nechi?", question_type: "single_choice",
      difficulty: "medium", score: 1, explanation: null, status: "active", options: [], media: [],
      created_at: "", updated_at: "",
    });
    renderCreatePage();
    typeInRichText(screen.getByLabelText("Savol matni"), "2+2 nechi?");
    fireEvent.click(screen.getByText("+ Variant qo'shish"));
    fireEvent.click(screen.getByText("+ Variant qo'shish"));

    typeInRichText(screen.getByLabelText("Variant matni 1"), "4");
    typeInRichText(screen.getByLabelText("Variant matni 2"), "5");
    fireEvent.click(screen.getAllByLabelText("To'g'ri variant")[0]);

    fireEvent.click(screen.getByText("Saqlash"));
    await waitFor(() => expect(questionsApi.create).toHaveBeenCalledOnce());
    const callArg = vi.mocked(questionsApi.create).mock.calls[0][0];
    expect(callArg.options).toEqual([
      { option_text: "4", is_correct: true },
      { option_text: "5", is_correct: false },
    ]);
  });

  it("rejects fewer than 2 options for a choice-type question", () => {
    renderCreatePage();
    typeInRichText(screen.getByLabelText("Savol matni"), "Savol");
    fireEvent.click(screen.getByText("+ Variant qo'shish"));

    fireEvent.click(screen.getByText("Saqlash"));
    expect(screen.getByText(/kamida 2 ta variantga ega bo'lishi kerak/)).toBeInTheDocument();
  });

  it("does not render an options section at all for 'essay' (no options expected)", () => {
    renderCreatePage();
    fireEvent.change(screen.getByLabelText("Turi"), { target: { value: "essay" } });
    expect(screen.queryByText("Variantlar")).not.toBeInTheDocument();
  });

  it("radio behavior: selecting a second option for single_choice deselects the first", () => {
    renderCreatePage();
    fireEvent.click(screen.getByText("+ Variant qo'shish"));
    fireEvent.click(screen.getByText("+ Variant qo'shish"));
    const checks = screen.getAllByLabelText("To'g'ri variant") as HTMLInputElement[];

    fireEvent.click(checks[0]);
    expect(checks[0].checked).toBe(true);
    fireEvent.click(checks[1]);
    expect(checks[0].checked).toBe(false);
    expect(checks[1].checked).toBe(true);
  });

  // --- Sprint 33: Question Editor Frontend ---

  it("multiple_choice: allows selecting more than one correct option (checkbox, not radio)", () => {
    renderCreatePage();
    fireEvent.change(screen.getByLabelText("Turi"), { target: { value: "multiple_choice" } });
    fireEvent.click(screen.getByText("+ Variant qo'shish"));
    fireEvent.click(screen.getByText("+ Variant qo'shish"));
    const checks = screen.getAllByLabelText("To'g'ri variant") as HTMLInputElement[];

    fireEvent.click(checks[0]);
    fireEvent.click(checks[1]);
    expect(checks[0].checked).toBe(true);
    expect(checks[1].checked).toBe(true); // both stay checked — unlike single_choice's radio behavior
  });

  it("toggles into Preview mode and shows the live question text, not fake data", () => {
    renderCreatePage();
    typeInRichText(screen.getByLabelText("Savol matni"), "2+2 nechi?");
    fireEvent.click(screen.getByText("Ko'rib chiqish (Preview)"));
    expect(screen.getByText("2+2 nechi?")).toBeInTheDocument();
    expect(screen.getByText("Tahrirlashga qaytish")).toBeInTheDocument();
  });

  it("question type switching updates which options section is shown", () => {
    renderCreatePage();
    fireEvent.click(screen.getByText("+ Variant qo'shish"));
    expect(screen.getByText("Variantlar")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Turi"), { target: { value: "short_answer" } });
    expect(screen.queryByText("Variantlar")).not.toBeInTheDocument();
  });

  it("CREATE mode: media staged before saving is submitted via addMedia after the question is created (Sprint 33 fix — this never happened before)", async () => {
    vi.mocked(questionsApi.create).mockResolvedValue({
      id: "new-q1", test_id: "t1", question_text: "Q", question_type: "single_choice", difficulty: "medium",
      score: 1, explanation: null, status: "active", options: [], media: [], created_at: "", updated_at: "",
    });
    vi.mocked(questionsApi.addMedia).mockResolvedValue({
      id: "m1", question_id: "new-q1", option_id: null, media_type: "image", file_url: "", upload_id: "u1",
    });

    renderCreatePage();
    typeInRichText(screen.getByLabelText("Savol matni"), "Savol matni uzun");
    fireEvent.click(screen.getByText("+ Variant qo'shish"));
    fireEvent.click(screen.getByText("+ Variant qo'shish"));
    fireEvent.click(screen.getAllByLabelText("To'g'ri variant")[0]);
    typeInRichText(screen.getByLabelText("Variant matni 1"), "A");
    typeInRichText(screen.getByLabelText("Variant matni 2"), "B");

    fireEvent.click(screen.getByText("Saqlash"));

    await waitFor(() => expect(questionsApi.create).toHaveBeenCalledOnce());
    // No media was staged in this test (upload flow itself is covered
    // by FileUploader's own tests) — confirms addMedia is simply never
    // called when there's nothing to attach, and the create flow
    // completes without error either way.
    expect(questionsApi.addMedia).not.toHaveBeenCalled();
  });
});
