import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { UsersListPage } from "./UsersListPage";
import { usersApi } from "@/api/users";
import { rolesApi } from "@/api/roles";

vi.mock("@/api/users");
vi.mock("@/api/roles");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <UsersListPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("UsersListPage", () => {
  beforeEach(() => {
    vi.mocked(rolesApi.list).mockResolvedValue([{ id: "r1", name: "Teacher", description: null, status: "active" }]);
    vi.mocked(usersApi.list).mockResolvedValue({
      items: [
        {
          id: "u1", role_id: "r1", first_name: "Aziz", last_name: "Karimov",
          phone: "+998901234567", email: null, gender: null, birth_date: null,
          image: null, status: "active", last_login: null, created_at: "2026-01-01T00:00:00Z",
        },
      ],
      meta: { page: 1, per_page: 20, total: 1, total_pages: 1 },
    });
  });

  it("renders the fetched user row", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("Aziz Karimov")).toBeInTheDocument());
  });

  it("NEVER renders a Create/Add User button anywhere on the page (approved decision — no backend support)", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("Aziz Karimov")).toBeInTheDocument());
    expect(screen.queryByText(/qo'shish/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/yaratish/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/add user/i)).not.toBeInTheDocument();
  });

  it("NEVER renders a Delete button anywhere on the page (approved decision — no backend support)", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("Aziz Karimov")).toBeInTheDocument());
    expect(screen.queryByText(/o'chirish/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/delete/i)).not.toBeInTheDocument();
  });

  it("shows an empty state when there are no users", async () => {
    vi.mocked(usersApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 } });
    renderPage();
    await waitFor(() => expect(screen.getByText("Foydalanuvchi topilmadi")).toBeInTheDocument());
  });
});
