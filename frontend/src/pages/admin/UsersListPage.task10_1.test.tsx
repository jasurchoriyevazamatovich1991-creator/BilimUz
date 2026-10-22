/** Task 10.1 — administrator-managed account creation in the admin panel. */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { UsersListPage } from "./UsersListPage";
import { usersApi } from "@/api/users";
import { rolesApi } from "@/api/roles";
import { useAuthStore } from "@/store/authStore";
import { creatableRoles } from "@/lib/registration";

vi.mock("@/api/users");
vi.mock("@/api/roles");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter><UsersListPage /></MemoryRouter>
    </QueryClientProvider>,
  );
}

function signIn(role: string) {
  useAuthStore.getState().setUser({ id: "me", first_name: "A", last_name: "B", phone: null, email: null, role });
}

describe("UsersListPage — create user (Task 10.1)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(rolesApi.list).mockResolvedValue([]);
    vi.mocked(usersApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 } });
  });

  it("lets an Admin create a Student or Teacher account", async () => {
    signIn("Admin");
    vi.mocked(usersApi.create).mockResolvedValue({} as never);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Foydalanuvchi qo'shish" }));
    const roleSelect = screen.getByLabelText("Rol") as HTMLSelectElement;
    expect(Array.from(roleSelect.options).map((o) => o.value)).toEqual(["Student", "Teacher"]);
    fireEvent.change(screen.getByLabelText("Ism"), { target: { value: "Nodira" } });
    fireEvent.change(screen.getByLabelText("Familiya"), { target: { value: "Karimova" } });
    fireEvent.change(screen.getByLabelText("Telefon (+998…)"), { target: { value: " +998901234567 " } });
    fireEvent.change(screen.getByLabelText("Boshlang'ich parol (kamida 12 belgi)"), { target: { value: "Strong-Pass-1234" } });
    fireEvent.change(roleSelect, { target: { value: "Teacher" } });
    fireEvent.click(screen.getByRole("button", { name: "Yaratish" }));
    await waitFor(() => expect(usersApi.create).toHaveBeenCalledWith({
      first_name: "Nodira", last_name: "Karimova", phone: "+998901234567", email: undefined,
      password: "Strong-Pass-1234", role: "Teacher",
    }));
    await waitFor(() => expect(screen.queryByTestId("create-user-form")).not.toBeInTheDocument());
  });

  it("offers Admin accounts only to a Super Admin", async () => {
    signIn("Super Admin");
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Foydalanuvchi qo'shish" }));
    expect(Array.from((screen.getByLabelText("Rol") as HTMLSelectElement).options).map((o) => o.value)).toEqual(["Student", "Teacher", "Admin"]);
  });

  it.each(["Moderator", "Teacher", "Student"])("shows no create button to %s", async (role) => {
    signIn(role);
    renderPage();
    await screen.findByText("Foydalanuvchilar");
    expect(screen.queryByRole("button", { name: "Foydalanuvchi qo'shish" })).not.toBeInTheDocument();
  });

  it("never offers Super Admin", () => {
    for (const r of ["Admin", "Super Admin", "Teacher", null]) expect(creatableRoles(r)).not.toContain("Super Admin");
  });
});
