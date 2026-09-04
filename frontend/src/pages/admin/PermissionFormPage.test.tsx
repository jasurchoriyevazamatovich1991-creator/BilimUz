import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PermissionFormPage } from "./PermissionFormPage";
import { permissionsApi } from "@/api/permissions";
import { useAuthStore } from "@/store/authStore";

vi.mock("@/api/permissions");

function renderCreatePage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/admin/permissions/new"]}>
        <Routes>
          <Route path="/admin/permissions/new" element={<PermissionFormPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function renderEditPage(permissionId = "p1") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/admin/permissions/${permissionId}`]}>
        <Routes>
          <Route path="/admin/permissions/:permissionId" element={<PermissionFormPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const MOCK_PERMISSION = { id: "p1", name: "Delete Users", code: "users.delete", module: "users", description: null, status: "active", created_at: "" };

describe("PermissionFormPage — Super Admin only", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Super Admin" });
  });

  it("creates a new permission with name, code, and module", async () => {
    vi.mocked(permissionsApi.create).mockResolvedValue(MOCK_PERMISSION);
    renderCreatePage();
    fireEvent.change(screen.getByLabelText("Nomi"), { target: { value: "Delete Users" } });
    fireEvent.change(screen.getByLabelText("Kod"), { target: { value: "users.delete" } });
    fireEvent.change(screen.getByLabelText("Modul"), { target: { value: "users" } });
    fireEvent.click(screen.getByText("Saqlash"));
    await waitFor(() =>
      expect(permissionsApi.create).toHaveBeenCalledWith({ name: "Delete Users", code: "users.delete", module: "users", description: undefined }),
    );
  });

  it("edits an existing permission's name", async () => {
    vi.mocked(permissionsApi.get).mockResolvedValue(MOCK_PERMISSION);
    vi.mocked(permissionsApi.update).mockResolvedValue(MOCK_PERMISSION);
    renderEditPage();
    await waitFor(() => expect(screen.getByDisplayValue("Delete Users")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("Nomi"), { target: { value: "Delete Any User" } });
    fireEvent.click(screen.getByText("Saqlash"));
    await waitFor(() => expect(permissionsApi.update).toHaveBeenCalledWith("p1", { name: "Delete Any User", description: undefined, status: "active" }));
  });

  it("shows code as plain read-only text in edit mode (immutable, matches backend)", async () => {
    vi.mocked(permissionsApi.get).mockResolvedValue(MOCK_PERMISSION);
    renderEditPage();
    await waitFor(() => expect(screen.getByText("users.delete")).toBeInTheDocument());
    expect(screen.queryByLabelText("Kod")).not.toBeInTheDocument();
  });

  it("deletes via ConfirmDialog, not a raw browser confirm", async () => {
    vi.mocked(permissionsApi.get).mockResolvedValue(MOCK_PERMISSION);
    vi.mocked(permissionsApi.remove).mockResolvedValue(undefined as never);
    renderEditPage();
    await waitFor(() => expect(screen.getByDisplayValue("Delete Users")).toBeInTheDocument());

    fireEvent.click(screen.getByText("O'chirish", { selector: "button" }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "O'chirish" }));
    await waitFor(() => expect(permissionsApi.remove).toHaveBeenCalledWith("p1"));
  });
});
