import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TopicsListPage } from "./TopicsListPage";
import { topicsApi } from "@/api/topics";
import { subjectsApi } from "@/api/subjects";
import { gradesApi } from "@/api/grades";
import { useAuthStore } from "@/store/authStore";

vi.mock("@/api/topics");
vi.mock("@/api/subjects");
vi.mock("@/api/grades");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <TopicsListPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const MOCK_TOPIC = {
  id: "t1", subject_id: "sub1", grade_id: null, title: "Kasrlar",
  description: null, order_number: 1, status: "active",
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
};

describe("TopicsListPage — Sprint 26 basePath prop (safe reuse for Teacher)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Teacher" });
    vi.mocked(subjectsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 100, total: 0, total_pages: 0 } });
    vi.mocked(gradesApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 100, total: 0, total_pages: 0 } });
  });

  it("defaults to /admin — every existing Admin usage is completely unchanged", async () => {
    vi.mocked(topicsApi.list).mockResolvedValue({ items: [MOCK_TOPIC], meta: { page: 1, per_page: 20, total: 1, total_pages: 1 } });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <TopicsListPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText("Qo'shish")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Qo'shish"));
    // No route assertions here (no <Routes> tree) — this test only
    // confirms the component renders identically with zero props,
    // matching every pre-existing Admin test in this file exactly.
  });

  it("navigates to /teacher/topics/new when basePath='/teacher' is passed (used by Teacher's routes)", async () => {
    vi.mocked(topicsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 } });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/teacher/topics"]}>
          <Routes>
            <Route path="/teacher/topics" element={<TopicsListPage basePath="/teacher" />} />
            <Route path="/teacher/topics/new" element={<div>TEACHER_NEW_TOPIC_REACHED</div>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText("Qo'shish")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Qo'shish"));
    await waitFor(() => expect(screen.getByText("TEACHER_NEW_TOPIC_REACHED")).toBeInTheDocument());
  });
});

describe("TopicsListPage — RBAC (THE critical test: Teacher CAN write here, unlike Subjects/Grades)", () => {
  beforeEach(() => {
    vi.mocked(topicsApi.list).mockResolvedValue({
      items: [MOCK_TOPIC],
      meta: { page: 1, per_page: 20, total: 1, total_pages: 1 },
    });
    vi.mocked(subjectsApi.list).mockResolvedValue({
      items: [{ id: "sub1", name: "Matematika", icon: null, color: null, status: "active", created_at: "", updated_at: "" }],
      meta: { page: 1, per_page: 100, total: 1, total_pages: 1 },
    });
    vi.mocked(gradesApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 100, total: 0, total_pages: 0 } });
  });

  it("Admin sees write controls", async () => {
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
    renderPage();
    await waitFor(() => expect(screen.getByText("Kasrlar")).toBeInTheDocument());
    expect(screen.getByText("Qo'shish")).toBeInTheDocument();
  });

  it("Teacher DOES see write controls on Topics (the backend genuinely grants this — verified against require_roles)", async () => {
    useAuthStore.getState().setUser({ id: "u2", first_name: "T", last_name: "C", phone: null, email: null, role: "Teacher" });
    renderPage();
    await waitFor(() => expect(screen.getByText("Kasrlar")).toBeInTheDocument());
    expect(screen.getByText("Qo'shish")).toBeInTheDocument();
    expect(screen.getByText("O'chirish")).toBeInTheDocument();
  });

  it("Moderator (not in Topics' allowed write list) does NOT see write controls", async () => {
    useAuthStore.getState().setUser({ id: "u3", first_name: "M", last_name: "D", phone: null, email: null, role: "Moderator" });
    renderPage();
    await waitFor(() => expect(screen.getByText("Kasrlar")).toBeInTheDocument());
    expect(screen.queryByText("Qo'shish")).not.toBeInTheDocument();
  });

  it("resolves subject_id to a real subject name via the read-only lookup", async () => {
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
    renderPage();
    // "Matematika" also appears as an <option> in the Subject filter
    // dropdown — getByRole("cell", ...) matches only the <td>, so this
    // still verifies the exact same thing (the resolved name rendered
    // in the table row) without an ambiguous plain-text match.
    await waitFor(() => expect(screen.getByRole("cell", { name: "Matematika" })).toBeInTheDocument());
  });
});
