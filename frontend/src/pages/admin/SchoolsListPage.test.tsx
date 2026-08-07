import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SchoolsListPage } from "./SchoolsListPage";
import { schoolsApi } from "@/api/schools";
import { useAuthStore } from "@/store/authStore";

vi.mock("@/api/schools");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SchoolsListPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const MOCK_SCHOOL = {
  id: "s1", name: "1-maktab", region: "Toshkent", district: "Chilonzor",
  address: null, phone: null, status: "active",
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
};

describe("SchoolsListPage — RBAC gating (approved decision 4)", () => {
  beforeEach(() => {
    vi.mocked(schoolsApi.list).mockResolvedValue({
      items: [MOCK_SCHOOL],
      meta: { page: 1, per_page: 20, total: 1, total_pages: 1 },
    });
  });

  it("Admin sees the 'Qo'shish' button and per-row 'O'chirish' action", async () => {
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
    renderPage();
    await waitFor(() => expect(screen.getByText("1-maktab")).toBeInTheDocument());
    expect(screen.getByText("Qo'shish")).toBeInTheDocument();
    expect(screen.getByText("O'chirish")).toBeInTheDocument();
  });

  it("Moderator sees NEITHER the 'Qo'shish' button NOR any 'O'chirish' action — hidden entirely, not disabled", async () => {
    useAuthStore.getState().setUser({ id: "u2", first_name: "M", last_name: "D", phone: null, email: null, role: "Moderator" });
    renderPage();
    await waitFor(() => expect(screen.getByText("1-maktab")).toBeInTheDocument());
    expect(screen.queryByText("Qo'shish")).not.toBeInTheDocument();
    expect(screen.queryByText("O'chirish")).not.toBeInTheDocument();
    // Not just missing text — the button must not exist as a disabled element either.
    expect(screen.queryByRole("button", { name: "Qo'shish" })).not.toBeInTheDocument();
  });

  it("Super Admin sees the same write controls as Admin", async () => {
    useAuthStore.getState().setUser({ id: "u3", first_name: "S", last_name: "A", phone: null, email: null, role: "Super Admin" });
    renderPage();
    await waitFor(() => expect(screen.getByText("1-maktab")).toBeInTheDocument());
    expect(screen.getByText("Qo'shish")).toBeInTheDocument();
  });
});
