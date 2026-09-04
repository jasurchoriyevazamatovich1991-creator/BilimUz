import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RolesListPage } from "./RolesListPage";
import { rolesApi } from "@/api/roles";
import { useAuthStore } from "@/store/authStore";

vi.mock("@/api/roles");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <RolesListPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const MOCK_ROLE = { id: "r1", name: "Teacher", description: "Teachers", status: "active" };

describe("RolesListPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("loads and shows a role row on success", async () => {
    vi.mocked(rolesApi.listPaginated).mockResolvedValue({
      items: [MOCK_ROLE], meta: { page: 1, per_page: 20, total: 1, total_pages: 1 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Teacher")).toBeInTheDocument());
  });

  it("shows an empty state when there are no roles", async () => {
    vi.mocked(rolesApi.listPaginated).mockResolvedValue({
      items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Rol topilmadi")).toBeInTheDocument());
  });

  it("shows ErrorState on API failure", async () => {
    vi.mocked(rolesApi.listPaginated).mockRejectedValue(new Error("network error"));
    renderPage();
    await waitFor(() => expect(screen.getByText("Rollar")).toBeInTheDocument());
  });

  it("Super Admin sees the 'Qo'shish' button", async () => {
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Super Admin" });
    vi.mocked(rolesApi.listPaginated).mockResolvedValue({
      items: [MOCK_ROLE], meta: { page: 1, per_page: 20, total: 1, total_pages: 1 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Qo'shish")).toBeInTheDocument());
  });

  it("plain Admin does NOT see the 'Qo'shish' button (Super Admin only, narrower than every prior module)", async () => {
    useAuthStore.getState().setUser({ id: "u2", first_name: "A", last_name: "D", phone: null, email: null, role: "Admin" });
    vi.mocked(rolesApi.listPaginated).mockResolvedValue({
      items: [MOCK_ROLE], meta: { page: 1, per_page: 20, total: 1, total_pages: 1 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Teacher")).toBeInTheDocument());
    expect(screen.queryByText("Qo'shish")).not.toBeInTheDocument();
  });

  it("marks a known system role as 'Tizim roli' in the list", async () => {
    vi.mocked(rolesApi.listPaginated).mockResolvedValue({
      items: [MOCK_ROLE], meta: { page: 1, per_page: 20, total: 1, total_pages: 1 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Tizim roli")).toBeInTheDocument());
  });
});
