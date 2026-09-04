import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PermissionsListPage } from "./PermissionsListPage";
import { permissionsApi } from "@/api/permissions";
import { useAuthStore } from "@/store/authStore";

vi.mock("@/api/permissions");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <PermissionsListPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const MOCK_PERMISSION = { id: "p1", name: "Delete Users", code: "users.delete", module: "users", description: null, status: "active", created_at: "" };

describe("PermissionsListPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Super Admin" });
  });

  it("loads and shows a permission row on success", async () => {
    vi.mocked(permissionsApi.list).mockResolvedValue({
      items: [MOCK_PERMISSION], meta: { page: 1, per_page: 20, total: 1, total_pages: 1 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Delete Users")).toBeInTheDocument());
  });

  it("shows an empty state when there are no permissions", async () => {
    vi.mocked(permissionsApi.list).mockResolvedValue({
      items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Ruxsat topilmadi")).toBeInTheDocument());
  });

  it("shows ErrorState on API failure", async () => {
    vi.mocked(permissionsApi.list).mockRejectedValue(new Error("network error"));
    renderPage();
    await waitFor(() => expect(screen.getByText("Ruxsatlar")).toBeInTheDocument());
  });

  it("plain Admin does not see write controls", async () => {
    useAuthStore.getState().setUser({ id: "u2", first_name: "A", last_name: "D", phone: null, email: null, role: "Admin" });
    vi.mocked(permissionsApi.list).mockResolvedValue({
      items: [MOCK_PERMISSION], meta: { page: 1, per_page: 20, total: 1, total_pages: 1 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Delete Users")).toBeInTheDocument());
    expect(screen.queryByText("Qo'shish")).not.toBeInTheDocument();
    expect(screen.queryByText("O'chirish")).not.toBeInTheDocument();
  });
});
