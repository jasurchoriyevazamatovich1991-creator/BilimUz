import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ExamConfigPage } from "./ExamConfigPage";
import { testsApi } from "@/api/tests";
import { examSectionsApi, examModulesApi, questionGroupsApi, routingThresholdRulesApi } from "@/api/examConfig";
import { useAuthStore } from "@/store/authStore";

vi.mock("@/api/tests");
vi.mock("@/api/examConfig");

const TEST_OUT = {
  id: "t1", subject_id: null, grade_id: null, topic_id: null, title: "SAT Mock", description: null,
  difficulty: "medium", duration: 60, question_count: 5, passing_score: null,
  shuffle_questions: true, shuffle_answers: true, status: "draft",
  created_at: "", updated_at: "",
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/admin/tests/t1/exam-config"]}>
        <Routes>
          <Route path="/admin/tests/:testId/exam-config" element={<ExamConfigPage />} />
          <Route path="/admin/tests" element={<div>Testlar ro'yxati sahifasi</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ExamConfigPage — Sprint 74", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(testsApi.get).mockResolvedValue(TEST_OUT);
    // Sprint 75 completion — default empty, so every pre-existing test
    // above (which doesn't care about routing rules) keeps working
    // unchanged; tests that DO care override this explicitly.
    vi.mocked(routingThresholdRulesApi.list).mockResolvedValue([]);
  });

  it("Admin can open the page and sees sections/groups empty states when there is no structure yet", async () => {
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
    vi.mocked(examSectionsApi.list).mockResolvedValue([]);
    vi.mocked(examModulesApi.listForTest).mockResolvedValue([]);
    vi.mocked(questionGroupsApi.list).mockResolvedValue([]);

    renderPage();

    await waitFor(() => expect(screen.getByText("SAT Mock")).toBeInTheDocument());
    expect(screen.getByText(/Bu test uchun hali bo'lim yo'q/)).toBeInTheDocument();
    expect(screen.getByText(/Bu test uchun hali guruh yo'q/)).toBeInTheDocument();
  });

  it("Teacher is redirected away (cannot read ExamSection/ExamModule/QuestionGroup per backend RBAC)", async () => {
    useAuthStore.getState().setUser({ id: "u2", first_name: "A", last_name: "B", phone: null, email: null, role: "Teacher" });
    vi.mocked(examSectionsApi.list).mockResolvedValue([]);
    vi.mocked(examModulesApi.listForTest).mockResolvedValue([]);
    vi.mocked(questionGroupsApi.list).mockResolvedValue([]);

    renderPage();

    await waitFor(() => expect(screen.getByText("Testlar ro'yxati sahifasi")).toBeInTheDocument());
    expect(examSectionsApi.list).not.toHaveBeenCalled();
  });

  it("Student is redirected away", async () => {
    useAuthStore.getState().setUser({ id: "u3", first_name: "A", last_name: "B", phone: null, email: null, role: "Student" });
    renderPage();
    await waitFor(() => expect(screen.getByText("Testlar ro'yxati sahifasi")).toBeInTheDocument());
  });

  it("renders existing sections and lets Admin expand a section to see its modules", async () => {
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Super Admin" });
    vi.mocked(examSectionsApi.list).mockResolvedValue([
      { id: "s1", test_id: "t1", name: "Reading and Writing", order_number: 0, duration: 35, created_at: "", updated_at: "" },
    ]);
    vi.mocked(examModulesApi.listForTest).mockResolvedValue([
      { id: "m1", section_id: "s1", name: "Module 1", order_number: 0, duration: 35, difficulty_tier: null, routing_group: "verbal", routing_variant: null, created_at: "", updated_at: "" },
    ]);
    vi.mocked(questionGroupsApi.list).mockResolvedValue([]);

    renderPage();
    await waitFor(() => expect(screen.getByText("Reading and Writing")).toBeInTheDocument());

    const user = userEvent.setup();
    await user.click(screen.getByText("Modullar (1)"));
    expect(screen.getByText("Module 1")).toBeInTheDocument();
    expect(screen.getByText(/routing_group: verbal/)).toBeInTheDocument();
  });

  it("creates a new section via the add form", async () => {
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
    vi.mocked(examSectionsApi.list).mockResolvedValue([]);
    vi.mocked(examModulesApi.listForTest).mockResolvedValue([]);
    vi.mocked(questionGroupsApi.list).mockResolvedValue([]);
    vi.mocked(examSectionsApi.create).mockResolvedValue({
      id: "s1", test_id: "t1", name: "Listening", order_number: 0, duration: null, created_at: "", updated_at: "",
    });

    renderPage();
    await waitFor(() => expect(screen.getByText("SAT Mock")).toBeInTheDocument());

    const user = userEvent.setup();
    await user.click(screen.getByText("+ Bo'lim qo'shish"));
    await user.type(screen.getByLabelText("Nomi"), "Listening");
    await user.click(screen.getByText("Saqlash"));

    await waitFor(() => expect(examSectionsApi.create).toHaveBeenCalledWith(
      expect.objectContaining({ test_id: "t1", name: "Listening" }),
    ));
  });

  it("deletes a question group via ConfirmDialog, not a raw browser confirm", async () => {
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
    vi.mocked(examSectionsApi.list).mockResolvedValue([]);
    vi.mocked(examModulesApi.listForTest).mockResolvedValue([]);
    vi.mocked(questionGroupsApi.list).mockResolvedValue([
      { id: "g1", test_id: "t1", module_id: null, title: "Passage 1", stimulus_text: "Once upon a time", order_number: 0, created_at: "", updated_at: "" },
    ]);
    vi.mocked(questionGroupsApi.remove).mockResolvedValue(undefined as never);

    renderPage();
    await waitFor(() => expect(screen.getByText("Passage 1")).toBeInTheDocument());

    const user = userEvent.setup();
    await user.click(screen.getByText("O'chirish"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.click(screen.getAllByText("O'chirish")[1]);

    await waitFor(() => expect(questionGroupsApi.remove).toHaveBeenCalledWith("g1"));
  });

  it("links to the existing Questions list rather than building a second question editor", async () => {
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
    vi.mocked(examSectionsApi.list).mockResolvedValue([]);
    vi.mocked(examModulesApi.listForTest).mockResolvedValue([]);
    vi.mocked(questionGroupsApi.list).mockResolvedValue([]);

    renderPage();
    await waitFor(() => expect(screen.getByText("Savollar ro'yxatini ochish")).toBeInTheDocument());
  });

  // --- Sprint 75 completion: Adaptive Routing Rules section ---

  describe("Adaptive Routing Rules (Sprint 75 completion)", () => {
    it("loads and displays existing rules for Admin", async () => {
      useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
      vi.mocked(examSectionsApi.list).mockResolvedValue([]);
      vi.mocked(examModulesApi.listForTest).mockResolvedValue([]);
      vi.mocked(questionGroupsApi.list).mockResolvedValue([]);
      vi.mocked(routingThresholdRulesApi.list).mockResolvedValue([
        { id: "r1", test_id: "t1", routing_group: "difficulty", min_ratio: 0.7, variant: "medium", created_at: "", updated_at: "" },
      ]);

      renderPage();

      await waitFor(() => expect(screen.getByText("difficulty")).toBeInTheDocument());
      expect(screen.getByText("0.70")).toBeInTheDocument();
      expect(screen.getByText("medium")).toBeInTheDocument();
    });

    it("loads and displays existing rules for Super Admin too", async () => {
      useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Super Admin" });
      vi.mocked(examSectionsApi.list).mockResolvedValue([]);
      vi.mocked(examModulesApi.listForTest).mockResolvedValue([]);
      vi.mocked(questionGroupsApi.list).mockResolvedValue([]);
      vi.mocked(routingThresholdRulesApi.list).mockResolvedValue([
        { id: "r1", test_id: "t1", routing_group: "difficulty", min_ratio: 0.9, variant: "hard", created_at: "", updated_at: "" },
      ]);

      renderPage();

      await waitFor(() => expect(screen.getByText("hard")).toBeInTheDocument());
    });

    it("Teacher cannot reach the configuration page at all (so cannot see or call the rules API)", async () => {
      useAuthStore.getState().setUser({ id: "u2", first_name: "A", last_name: "B", phone: null, email: null, role: "Teacher" });

      renderPage();

      await waitFor(() => expect(screen.getByText("Testlar ro'yxati sahifasi")).toBeInTheDocument());
      expect(routingThresholdRulesApi.list).not.toHaveBeenCalled();
    });

    it("creates a new rule via the add form", async () => {
      useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
      vi.mocked(examSectionsApi.list).mockResolvedValue([]);
      vi.mocked(examModulesApi.listForTest).mockResolvedValue([]);
      vi.mocked(questionGroupsApi.list).mockResolvedValue([]);
      vi.mocked(routingThresholdRulesApi.list).mockResolvedValue([]);
      vi.mocked(routingThresholdRulesApi.create).mockResolvedValue({
        id: "r1", test_id: "t1", routing_group: "difficulty", min_ratio: 0.7, variant: "medium", created_at: "", updated_at: "",
      });

      renderPage();
      await waitFor(() => expect(screen.getByText("+ Qoida qo'shish")).toBeInTheDocument());

      const user = userEvent.setup();
      await user.click(screen.getByText("+ Qoida qo'shish"));
      await user.type(screen.getByLabelText("routing_group"), "difficulty");
      await user.type(screen.getByLabelText("Minimal nisbat (0.00 – 1.00)"), "0.7");
      await user.type(screen.getByLabelText("Maqsadli variant (routing_variant)"), "medium");
      await user.click(screen.getByText("Saqlash"));

      await waitFor(() => expect(routingThresholdRulesApi.create).toHaveBeenCalledWith(
        expect.objectContaining({ test_id: "t1", routing_group: "difficulty", min_ratio: 0.7, variant: "medium" }),
      ));
    });

    it("rejects an out-of-range min_ratio client-side without calling the API", async () => {
      useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
      vi.mocked(examSectionsApi.list).mockResolvedValue([]);
      vi.mocked(examModulesApi.listForTest).mockResolvedValue([]);
      vi.mocked(questionGroupsApi.list).mockResolvedValue([]);
      vi.mocked(routingThresholdRulesApi.list).mockResolvedValue([]);

      renderPage();
      await waitFor(() => expect(screen.getByText("+ Qoida qo'shish")).toBeInTheDocument());

      const user = userEvent.setup();
      await user.click(screen.getByText("+ Qoida qo'shish"));
      await user.type(screen.getByLabelText("routing_group"), "difficulty");
      await user.type(screen.getByLabelText("Minimal nisbat (0.00 – 1.00)"), "1.5");
      await user.type(screen.getByLabelText("Maqsadli variant (routing_variant)"), "medium");
      await user.click(screen.getByText("Saqlash"));

      expect(await screen.findByText(/0 va 1 orasida/)).toBeInTheDocument();
      expect(routingThresholdRulesApi.create).not.toHaveBeenCalled();
    });

    it("edits an existing rule", async () => {
      useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
      vi.mocked(examSectionsApi.list).mockResolvedValue([]);
      vi.mocked(examModulesApi.listForTest).mockResolvedValue([]);
      vi.mocked(questionGroupsApi.list).mockResolvedValue([]);
      vi.mocked(routingThresholdRulesApi.list).mockResolvedValue([
        { id: "r1", test_id: "t1", routing_group: "difficulty", min_ratio: 0.7, variant: "medium", created_at: "", updated_at: "" },
      ]);
      vi.mocked(routingThresholdRulesApi.update).mockResolvedValue({
        id: "r1", test_id: "t1", routing_group: "difficulty", min_ratio: 0.8, variant: "medium", created_at: "", updated_at: "",
      });

      renderPage();
      await waitFor(() => expect(screen.getByText("difficulty")).toBeInTheDocument());

      const user = userEvent.setup();
      await user.click(screen.getByText("Tahrirlash"));
      const ratioInput = screen.getByLabelText("Minimal nisbat (0.00 – 1.00)");
      await user.clear(ratioInput);
      await user.type(ratioInput, "0.8");
      await user.click(screen.getByText("Saqlash"));

      await waitFor(() => expect(routingThresholdRulesApi.update).toHaveBeenCalledWith(
        "r1", expect.objectContaining({ min_ratio: 0.8 }),
      ));
    });

    it("deletes a rule via ConfirmDialog, not a raw browser confirm", async () => {
      useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
      vi.mocked(examSectionsApi.list).mockResolvedValue([]);
      vi.mocked(examModulesApi.listForTest).mockResolvedValue([]);
      vi.mocked(questionGroupsApi.list).mockResolvedValue([]);
      vi.mocked(routingThresholdRulesApi.list).mockResolvedValue([
        { id: "r1", test_id: "t1", routing_group: "difficulty", min_ratio: 0.7, variant: "medium", created_at: "", updated_at: "" },
      ]);
      vi.mocked(routingThresholdRulesApi.remove).mockResolvedValue(undefined as never);

      renderPage();
      await waitFor(() => expect(screen.getByText("difficulty")).toBeInTheDocument());

      const user = userEvent.setup();
      await user.click(screen.getByText("O'chirish"));
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      await user.click(screen.getAllByText("O'chirish")[1]);

      await waitFor(() => expect(routingThresholdRulesApi.remove).toHaveBeenCalledWith("r1"));
    });
  });
});

describe("ExamConfigPage — Task 4 scaled scoring configuration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
    vi.mocked(routingThresholdRulesApi.list).mockResolvedValue([]);
    vi.mocked(examModulesApi.listForTest).mockResolvedValue([]);
    vi.mocked(questionGroupsApi.list).mockResolvedValue([]);
  });

  it("without a profile the section form has no component select", async () => {
    vi.mocked(testsApi.get).mockResolvedValue(TEST_OUT);
    vi.mocked(examSectionsApi.list).mockResolvedValue([]);
    renderPage();
    await waitFor(() => expect(screen.getByText("SAT Mock")).toBeInTheDocument());
    expect(screen.getByLabelText("Profil")).toHaveValue("");
    await userEvent.setup().click(screen.getByText("+ Bo'lim qo'shish"));
    expect(screen.queryByLabelText("Ballash komponenti")).not.toBeInTheDocument();
  });

  it("with a SAT profile a new section can be created with a SAT component only", async () => {
    vi.mocked(testsApi.get).mockResolvedValue({ ...TEST_OUT, scoring_profile: "sat" });
    vi.mocked(examSectionsApi.list).mockResolvedValue([]);
    vi.mocked(examSectionsApi.create).mockResolvedValue({
      id: "s9", test_id: "t1", name: "Math", order_number: 0, duration: null, score_component: "sat_math", created_at: "", updated_at: "",
    });
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => expect(screen.getByLabelText("Profil")).toHaveValue("sat"));
    await user.click(screen.getByText("+ Bo'lim qo'shish"));

    const select = screen.getByLabelText("Ballash komponenti");
    const values = Array.from((select as HTMLSelectElement).options).map((o) => o.value);
    expect(values).toEqual(["", "sat_reading_writing", "sat_math"]);

    await user.type(screen.getByLabelText("Nomi"), "Math");
    await user.selectOptions(select, "sat_math");
    await user.click(screen.getByText("Saqlash"));
    await waitFor(() => expect(examSectionsApi.create).toHaveBeenCalledWith(expect.objectContaining({ name: "Math", score_component: "sat_math" })));
  });

  it("shows the tables button only for table-convertible components", async () => {
    vi.mocked(testsApi.get).mockResolvedValue({ ...TEST_OUT, scoring_profile: "ielts" });
    vi.mocked(examSectionsApi.list).mockResolvedValue([
      { id: "s1", test_id: "t1", name: "Listening", order_number: 0, duration: null, score_component: "ielts_listening", created_at: "", updated_at: "" },
      { id: "s2", test_id: "t1", name: "Writing", order_number: 1, duration: null, score_component: "ielts_writing", created_at: "", updated_at: "" },
    ]);
    renderPage();
    await waitFor(() => expect(screen.getByText("Listening")).toBeInTheDocument());
    expect(screen.getAllByText("Shkala jadvallari")).toHaveLength(1);
    expect(screen.getByText(/IELTS Writing/)).toBeInTheDocument();
  });
});

describe("ExamConfigPage — Task 6 calculator flag", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
    vi.mocked(testsApi.get).mockResolvedValue({ ...TEST_OUT, scoring_profile: "sat" });
    vi.mocked(routingThresholdRulesApi.list).mockResolvedValue([]);
    vi.mocked(examModulesApi.listForTest).mockResolvedValue([]);
    vi.mocked(questionGroupsApi.list).mockResolvedValue([]);
  });

  it("is off by default and is sent only when the admin ticks it", async () => {
    vi.mocked(examSectionsApi.list).mockResolvedValue([]);
    vi.mocked(examSectionsApi.create).mockResolvedValue({
      id: "s9", test_id: "t1", name: "Math", order_number: 0, duration: null, calculator_enabled: true, created_at: "", updated_at: "",
    });
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => expect(screen.getByLabelText("Profil")).toHaveValue("sat"));
    await user.click(screen.getByText("+ Bo'lim qo'shish"));
    const box = screen.getByLabelText("Imtihon davomida kalkulyatorga ruxsat berish");
    expect(box).not.toBeChecked();
    await user.type(screen.getByLabelText("Nomi"), "Math");
    await user.click(box);
    await user.click(screen.getByText("Saqlash"));
    await waitFor(() => expect(examSectionsApi.create).toHaveBeenCalledWith(expect.objectContaining({ name: "Math", calculator_enabled: true })));
  });

  it("shows the flag on a section and lets the admin switch it off", async () => {
    vi.mocked(examSectionsApi.list).mockResolvedValue([
      { id: "s1", test_id: "t1", name: "Math", order_number: 0, duration: null, score_component: "sat_math", calculator_enabled: true, created_at: "", updated_at: "" },
    ]);
    vi.mocked(examSectionsApi.update).mockResolvedValue({
      id: "s1", test_id: "t1", name: "Math", order_number: 0, duration: null, calculator_enabled: false, created_at: "", updated_at: "",
    });
    const user = userEvent.setup();
    renderPage();
    expect(await screen.findByText(/· Kalkulyator/)).toBeInTheDocument();
    await user.click(screen.getAllByText("Tahrirlash")[0]);
    const box = screen.getByLabelText("Imtihon davomida kalkulyatorga ruxsat berish");
    expect(box).toBeChecked();
    await user.click(box);
    await user.click(screen.getByText("Saqlash"));
    await waitFor(() => expect(examSectionsApi.update).toHaveBeenCalledWith("s1", expect.objectContaining({ calculator_enabled: false })));
  });
});
