/**
 * Sprint 74 — tests for the exam-structure assignment block added to
 * QuestionFormPage.tsx (edit mode only, Admin/Super Admin only — see
 * that file's own comments for why Teacher doesn't get this block).
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { QuestionFormPage } from "./QuestionFormPage";
import { questionsApi, type QuestionOut } from "@/api/questions";
import { examSectionsApi, examModulesApi, questionGroupsApi } from "@/api/examConfig";
import { useAuthStore } from "@/store/authStore";

vi.mock("@/api/questions");
vi.mock("@/api/examConfig");

const BASE_QUESTION: QuestionOut = {
  id: "q1", test_id: "t1", question_text: "Savol matni bu yerda", question_type: "essay",
  difficulty: "medium", score: 1, explanation: null, status: "active",
  section_id: null, module_id: null, group_id: null, options: [], media: [],
  created_at: "", updated_at: "",
};

function renderEditPage(role: string, question: QuestionOut = BASE_QUESTION) {
  useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role });
  vi.mocked(questionsApi.get).mockResolvedValue(question);
  vi.mocked(examSectionsApi.list).mockResolvedValue([
    { id: "s1", test_id: "t1", name: "Reading", order_number: 0, duration: null, created_at: "", updated_at: "" },
    { id: "s2", test_id: "t1", name: "Writing", order_number: 1, duration: null, created_at: "", updated_at: "" },
  ]);
  vi.mocked(examModulesApi.listForTest).mockResolvedValue([
    { id: "m1", section_id: "s1", name: "Module 1", order_number: 0, duration: null, difficulty_tier: null, routing_group: null, routing_variant: null, created_at: "", updated_at: "" },
    { id: "m2", section_id: "s2", name: "Module 2", order_number: 0, duration: null, difficulty_tier: null, routing_group: null, routing_variant: null, created_at: "", updated_at: "" },
  ]);
  vi.mocked(questionGroupsApi.list).mockResolvedValue([
    { id: "g1", test_id: "t1", module_id: "m1", title: "Passage 1", stimulus_text: null, order_number: 0, created_at: "", updated_at: "" },
  ]);

  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/admin/tests/t1/questions/q1"]}>
        <Routes>
          <Route path="/admin/tests/:testId/questions/:questionId" element={<QuestionFormPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("QuestionFormPage — Sprint 74 exam-structure assignment", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("Admin sees the assignment block with Bo'lim/Modul/Guruh selects in edit mode", async () => {
    renderEditPage("Admin");
    await waitFor(() => expect(screen.getByText("Imtihon tuzilmasiga biriktirish (ixtiyoriy)")).toBeInTheDocument());
    expect(screen.getByLabelText("Bo'lim")).toBeInTheDocument();
    expect(screen.getByLabelText("Modul")).toBeInTheDocument();
    expect(screen.getByLabelText("Guruh")).toBeInTheDocument();
  });

  it("Teacher does NOT see the assignment block (cannot list sections/modules/groups per backend RBAC)", async () => {
    renderEditPage("Teacher");
    await waitFor(() => expect(screen.getByText("Savolni tahrirlash")).toBeInTheDocument());
    expect(screen.queryByText("Imtihon tuzilmasiga biriktirish (ixtiyoriy)")).not.toBeInTheDocument();
    expect(examSectionsApi.list).not.toHaveBeenCalled();
  });

  it("pre-selects the question's current assignment", async () => {
    renderEditPage("Admin", { ...BASE_QUESTION, section_id: "s1", module_id: "m1", group_id: "g1" });
    await waitFor(() => expect(screen.getByLabelText("Bo'lim")).toHaveValue("s1"));
    expect(screen.getByLabelText("Modul")).toHaveValue("m1");
    expect(screen.getByLabelText("Guruh")).toHaveValue("g1");
  });

  it("module choices are filtered to the selected section", async () => {
    renderEditPage("Admin");
    await waitFor(() => expect(screen.getByLabelText("Bo'lim")).toBeInTheDocument());
    // No section selected yet — both modules are offered.
    const moduleSelect = screen.getByLabelText("Modul") as HTMLSelectElement;
    expect(moduleSelect.options.length).toBe(3); // placeholder + 2 modules
  });

  it("clearing a question's assignment sends explicit nulls, not an omitted field", async () => {
    renderEditPage("Admin", { ...BASE_QUESTION, section_id: "s1", module_id: "m1", group_id: "g1" });
    await waitFor(() => expect(screen.getByLabelText("Bo'lim")).toHaveValue("s1"));
    vi.mocked(questionsApi.update).mockResolvedValue({ ...BASE_QUESTION, section_id: "s1", module_id: "m1", group_id: "g1" });

    const user = (await import("@testing-library/user-event")).default.setup();
    await user.selectOptions(screen.getByLabelText("Bo'lim"), "");
    await user.click(screen.getByText("Saqlash"));

    await waitFor(() => expect(questionsApi.update).toHaveBeenCalled());
    const payload = vi.mocked(questionsApi.update).mock.calls[0][1];
    expect(payload.section_id).toBeNull();
  });
});
