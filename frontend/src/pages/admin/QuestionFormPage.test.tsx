import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { QuestionFormPage } from "./QuestionFormPage";
import { questionsApi } from "@/api/questions";
import { useAuthStore } from "@/store/authStore";

vi.mock("@/api/questions");

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
    fireEvent.change(screen.getByLabelText("Savol matni"), { target: { value: "2+2 nechi?" } });
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
    fireEvent.change(screen.getByLabelText("Savol matni"), { target: { value: "2+2 nechi?" } });
    fireEvent.click(screen.getByText("+ Variant qo'shish"));
    fireEvent.click(screen.getByText("+ Variant qo'shish"));

    const optionInputs = screen.getAllByPlaceholderText("Variant matni");
    fireEvent.change(optionInputs[0], { target: { value: "4" } });
    fireEvent.change(optionInputs[1], { target: { value: "5" } });
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
    fireEvent.change(screen.getByLabelText("Savol matni"), { target: { value: "Savol" } });
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
});
