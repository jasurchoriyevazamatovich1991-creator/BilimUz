import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LessonsListPage } from "./LessonsListPage";
import { lessonsApi } from "@/api/lessons";
import { topicsApi } from "@/api/topics";
import { useAuthStore } from "@/store/authStore";

vi.mock("@/api/lessons");
vi.mock("@/api/topics");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <LessonsListPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const MOCK_LESSON = {
  id: "l1", topic_id: "t1", title: "Kirish darsi", video: "https://x.com/v", pdf: null, content: null,
  status: "active", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
};

describe("LessonsListPage — RBAC (Teacher CAN write here, matches Topics not Subjects/Grades)", () => {
  beforeEach(() => {
    vi.mocked(lessonsApi.list).mockResolvedValue({
      items: [MOCK_LESSON],
      meta: { page: 1, per_page: 20, total: 1, total_pages: 1 },
    });
    vi.mocked(topicsApi.list).mockResolvedValue({
      items: [{ id: "t1", subject_id: "s1", grade_id: null, title: "1-mavzu", description: null, order_number: 1, status: "active", created_at: "", updated_at: "" }],
      meta: { page: 1, per_page: 100, total: 1, total_pages: 1 },
    });
  });

  it("Admin sees write controls", async () => {
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
    renderPage();
    await waitFor(() => expect(screen.getByText("Kirish darsi")).toBeInTheDocument());
    expect(screen.getByText("Qo'shish")).toBeInTheDocument();
  });

  it("Teacher DOES see write controls (backend genuinely grants this)", async () => {
    useAuthStore.getState().setUser({ id: "u2", first_name: "T", last_name: "C", phone: null, email: null, role: "Teacher" });
    renderPage();
    await waitFor(() => expect(screen.getByText("Kirish darsi")).toBeInTheDocument());
    expect(screen.getByText("Qo'shish")).toBeInTheDocument();
    expect(screen.getByText("O'chirish")).toBeInTheDocument();
  });

  it("Student is read-only (no write controls)", async () => {
    useAuthStore.getState().setUser({ id: "u3", first_name: "S", last_name: "D", phone: null, email: null, role: "Student" });
    renderPage();
    await waitFor(() => expect(screen.getByText("Kirish darsi")).toBeInTheDocument());
    expect(screen.queryByText("Qo'shish")).not.toBeInTheDocument();
    expect(screen.queryByText("O'chirish")).not.toBeInTheDocument();
  });

  it("shows the content badge for the lesson's video field", async () => {
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
    renderPage();
    await waitFor(() => expect(screen.getByText("Video")).toBeInTheDocument());
  });
});
