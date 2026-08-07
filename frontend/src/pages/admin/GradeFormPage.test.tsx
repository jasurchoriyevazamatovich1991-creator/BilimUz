import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { GradeFormPage } from "./GradeFormPage";
import { gradesApi } from "@/api/grades";
import { useAuthStore } from "@/store/authStore";

vi.mock("@/api/grades");

function renderEditPage(gradeId = "g1") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/admin/grades/${gradeId}`]}>
        <Routes>
          <Route path="/admin/grades/:gradeId" element={<GradeFormPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("GradeFormPage — name immutability (approved decision 4)", () => {
  beforeEach(() => {
    useAuthStore.getState().setUser({ id: "u1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
    vi.mocked(gradesApi.get).mockResolvedValue({
      id: "g1", name: "5-sinf", status: "active", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
    });
  });

  it("renders the name as plain text, not an input", async () => {
    renderEditPage();
    await waitFor(() => expect(screen.getByText("5-sinf")).toBeInTheDocument());
    // A plain <p> text node, not a form control — queryByRole('textbox') must not find it.
    expect(screen.queryByRole("textbox", { name: /nomi/i })).not.toBeInTheDocument();
  });

  it("shows an explanatory note that the name cannot be changed", async () => {
    renderEditPage();
    await waitFor(() => expect(screen.getByText("5-sinf")).toBeInTheDocument());
    expect(screen.getByText(/o'zgartirilmaydi/i)).toBeInTheDocument();
  });

  it("still allows editing status", async () => {
    renderEditPage();
    await waitFor(() => expect(screen.getByText("5-sinf")).toBeInTheDocument());
    expect(screen.getByLabelText("Holat")).toBeEnabled();
  });
});
