import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SubjectsListPage } from "./SubjectsListPage";
import { subjectsApi } from "@/api/subjects";
import { useAuthStore } from "@/store/authStore";

vi.mock("@/api/subjects");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SubjectsListPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const MOCK_SUBJECT = {
  id: "sub1", name: "Matematika", icon: null, color: "#0c447c", status: "active",
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
};

describe("SubjectsListPage — RBAC (Teacher is READ ONLY, unlike Topics)", () => {
  beforeEach(() => {
    vi.mocked(subjectsApi.list).mockResolvedValue({
      items: [MOCK_SUBJECT],
      meta: { page: 1, per_page: 20, total: 1, total_pages: 1 },
    });
  });

  it("Admin sees write controls", async () => {
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
    renderPage();
    await waitFor(() => expect(screen.getByText("Matematika")).toBeInTheDocument());
    expect(screen.getByText("Qo'shish")).toBeInTheDocument();
  });

  it("Teacher does NOT see write controls on Subjects (unlike on Topics)", async () => {
    useAuthStore.getState().setUser({ id: "u2", first_name: "T", last_name: "C", phone: null, email: null, role: "Teacher" });
    renderPage();
    await waitFor(() => expect(screen.getByText("Matematika")).toBeInTheDocument());
    expect(screen.queryByText("Qo'shish")).not.toBeInTheDocument();
    expect(screen.queryByText("O'chirish")).not.toBeInTheDocument();
  });
});
