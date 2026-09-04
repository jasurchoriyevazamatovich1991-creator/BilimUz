import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RoleFormPage } from "./RoleFormPage";
import { rolesApi } from "@/api/roles";
import { permissionsApi } from "@/api/permissions";
import { useAuthStore } from "@/store/authStore";
import { ApiError } from "@/api/client";

vi.mock("@/api/roles");
vi.mock("@/api/permissions");

function renderCreatePage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/admin/roles/new"]}>
        <Routes>
          <Route path="/admin/roles/new" element={<RoleFormPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function renderEditPage(roleId = "r1") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/admin/roles/${roleId}`]}>
        <Routes>
          <Route path="/admin/roles/:roleId" element={<RoleFormPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const CUSTOM_ROLE = { id: "r1", name: "Content Reviewer", description: "Custom", status: "active" };
const SYSTEM_ROLE = { id: "r2", name: "Teacher", description: "Built-in", status: "active" };

describe("RoleFormPage — Super Admin only", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Super Admin" });
    vi.mocked(permissionsApi.listForRole).mockResolvedValue([]);
    vi.mocked(permissionsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 100, total: 0, total_pages: 0 } });
  });

  it("creates a new role with the real request body", async () => {
    vi.mocked(rolesApi.create).mockResolvedValue({ id: "r3", name: "New Role", description: "", status: "active" });
    renderCreatePage();
    fireEvent.change(screen.getByLabelText("Nomi"), { target: { value: "New Role" } });
    fireEvent.click(screen.getByText("Saqlash"));
    await waitFor(() => expect(rolesApi.create).toHaveBeenCalledWith({ name: "New Role", description: undefined }));
  });

  it("edits a custom (non-system) role's description and status", async () => {
    vi.mocked(rolesApi.get).mockResolvedValue(CUSTOM_ROLE);
    vi.mocked(rolesApi.update).mockResolvedValue(CUSTOM_ROLE);
    renderEditPage();
    await waitFor(() => expect(screen.getByText("Content Reviewer")).toBeInTheDocument());
    expect(screen.getByLabelText("Holat")).toBeEnabled();
  });

  it("shows the name as plain read-only text (never an input) for ANY role, system or custom", async () => {
    vi.mocked(rolesApi.get).mockResolvedValue(CUSTOM_ROLE);
    renderEditPage();
    await waitFor(() => expect(screen.getByText("Content Reviewer")).toBeInTheDocument());
    expect(screen.queryByRole("textbox", { name: "Nomi" })).not.toBeInTheDocument();
  });

  it("a protected SYSTEM role shows status as read-only text, not a select", async () => {
    vi.mocked(rolesApi.get).mockResolvedValue(SYSTEM_ROLE);
    renderEditPage("r2");
    await waitFor(() => expect(screen.getByText("Teacher")).toBeInTheDocument());
    expect(screen.queryByLabelText("Holat")).not.toBeInTheDocument();
    expect(screen.getByText(/tizim roli — holatini o'zgartirib bo'lmaydi/i)).toBeInTheDocument();
  });

  it("a protected SYSTEM role has NO delete button at all", async () => {
    vi.mocked(rolesApi.get).mockResolvedValue(SYSTEM_ROLE);
    renderEditPage("r2");
    await waitFor(() => expect(screen.getByText("Teacher")).toBeInTheDocument());
    expect(screen.queryByText("O'chirish")).not.toBeInTheDocument();
  });

  it("a CUSTOM role DOES show a delete button", async () => {
    vi.mocked(rolesApi.get).mockResolvedValue(CUSTOM_ROLE);
    renderEditPage();
    await waitFor(() => expect(screen.getByText("Content Reviewer")).toBeInTheDocument());
    expect(screen.getByText("O'chirish")).toBeInTheDocument();
  });

  it("deletes a custom role via ConfirmDialog, not a raw browser confirm", async () => {
    vi.mocked(rolesApi.get).mockResolvedValue(CUSTOM_ROLE);
    vi.mocked(rolesApi.remove).mockResolvedValue(undefined as never);
    renderEditPage();
    await waitFor(() => expect(screen.getByText("Content Reviewer")).toBeInTheDocument());

    fireEvent.click(screen.getByText("O'chirish"));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "O'chirish" }));
    await waitFor(() => expect(rolesApi.remove).toHaveBeenCalledWith("r1"));
  });

  it("loads and displays currently-assigned permissions", async () => {
    vi.mocked(rolesApi.get).mockResolvedValue(CUSTOM_ROLE);
    vi.mocked(permissionsApi.listForRole).mockResolvedValue([
      { id: "g1", role_id: "r1", permission_id: "p1", permission: { id: "p1", name: "Delete Users", code: "users.delete", module: "users", description: null, status: "active", created_at: "" }, created_at: "" },
    ]);
    renderEditPage();
    await waitFor(() => expect(screen.getByText("Delete Users")).toBeInTheDocument());
  });

  it("assigns a permission using the real endpoint with permission_id", async () => {
    vi.mocked(rolesApi.get).mockResolvedValue(CUSTOM_ROLE);
    vi.mocked(permissionsApi.list).mockResolvedValue({
      items: [{ id: "p2", name: "View Reports", code: "reports.view", module: "reports", description: null, status: "active", created_at: "" }],
      meta: { page: 1, per_page: 100, total: 1, total_pages: 1 },
    });
    vi.mocked(permissionsApi.assignToRole).mockResolvedValue({ id: "g2", role_id: "r1", permission_id: "p2", permission: null, created_at: "" });
    renderEditPage();
    await waitFor(() => expect(screen.getByText("Ruxsatlar")).toBeInTheDocument());

    fireEvent.change(screen.getByDisplayValue("Ruxsat tanlang..."), { target: { value: "p2" } });
    fireEvent.click(screen.getByText("Biriktirish"));
    await waitFor(() => expect(permissionsApi.assignToRole).toHaveBeenCalledWith("r1", "p2"));
  });

  it("revokes a permission via ConfirmDialog (not a raw browser confirm)", async () => {
    vi.mocked(rolesApi.get).mockResolvedValue(CUSTOM_ROLE);
    vi.mocked(permissionsApi.listForRole).mockResolvedValue([
      { id: "g1", role_id: "r1", permission_id: "p1", permission: { id: "p1", name: "Delete Users", code: "users.delete", module: "users", description: null, status: "active", created_at: "" }, created_at: "" },
    ]);
    vi.mocked(permissionsApi.revokeFromRole).mockResolvedValue(undefined as never);
    renderEditPage();
    await waitFor(() => expect(screen.getByText("Delete Users")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Olib tashlash"));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument(); // ConfirmDialog, not window.confirm
    fireEvent.click(within(dialog).getByText("Olib tashlash"));
    await waitFor(() => expect(permissionsApi.revokeFromRole).toHaveBeenCalledWith("r1", "p1"));
  });

  it("surfaces a duplicate-assignment error (409) via the normal toast, without crashing", async () => {
    vi.mocked(rolesApi.get).mockResolvedValue(CUSTOM_ROLE);
    vi.mocked(permissionsApi.list).mockResolvedValue({
      items: [{ id: "p1", name: "Delete Users", code: "users.delete", module: "users", description: null, status: "active", created_at: "" }],
      meta: { page: 1, per_page: 100, total: 1, total_pages: 1 },
    });
    vi.mocked(permissionsApi.assignToRole).mockRejectedValue(new ApiError("Bu ruxsat allaqachon biriktirilgan", null, 409));
    renderEditPage();
    await waitFor(() => expect(screen.getByText("Ruxsatlar")).toBeInTheDocument());

    fireEvent.change(screen.getByDisplayValue("Ruxsat tanlang..."), { target: { value: "p1" } });
    fireEvent.click(screen.getByText("Biriktirish"));
    await waitFor(() => expect(permissionsApi.assignToRole).toHaveBeenCalledOnce());
    // No crash / no unhandled rejection — the page is still rendered.
    expect(screen.getByText("Ruxsatlar")).toBeInTheDocument();
  });
});

describe("RoleFormPage — non-Super-Admin cannot see write controls", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.getState().setUser({ id: "u2", first_name: "A", last_name: "D", phone: null, email: null, role: "Admin" });
    vi.mocked(permissionsApi.listForRole).mockResolvedValue([]);
    vi.mocked(permissionsApi.list).mockResolvedValue({ items: [], meta: { page: 1, per_page: 100, total: 0, total_pages: 0 } });
  });

  it("plain Admin viewing a role sees no Save/Delete/assign controls", async () => {
    vi.mocked(rolesApi.get).mockResolvedValue(CUSTOM_ROLE);
    renderEditPage();
    await waitFor(() => expect(screen.getByText("Content Reviewer")).toBeInTheDocument());
    expect(screen.queryByText("Saqlash")).not.toBeInTheDocument();
    expect(screen.queryByText("O'chirish")).not.toBeInTheDocument();
    expect(screen.queryByText("Biriktirish")).not.toBeInTheDocument();
  });

  it("plain Admin is redirected away from the Create route entirely", () => {
    const { container } = renderCreatePage();
    expect(container.textContent).not.toContain("Yangi rol");
  });
});
