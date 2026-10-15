/**
 * Student self-view (Admin Management of Mock Test Entitlements, Task
 * D, spec §5). Asserts the page is read-only — no revoke/extend/grant
 * controls appear anywhere, even though the underlying data is exactly
 * the same EntitlementOut shape the admin panel renders.
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import { MockTestEntitlementsPage } from "./MockTestEntitlementsPage";
import { entitlementsApi, type EntitlementOut } from "@/api/entitlements";

vi.mock("@/api/entitlements");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MockTestEntitlementsPage />
    </QueryClientProvider>,
  );
}

const ENTITLEMENT: EntitlementOut = {
  id: "e1", user_id: "me", product_id: "p1", source: "admin_grant",
  granted_by: "admin-1", payment_id: null, status: "active",
  start_date: "2026-01-01T00:00:00Z", end_date: "2026-12-31T00:00:00Z", reason: null,
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
  product_name: "IELTS Mock Test", product_type: "mock_test",
  subject_id: "s1", subject_name: "IELTS", granted_by_name: "Admin Adminov",
  effective_status: "active",
};

describe("MockTestEntitlementsPage (student self-view)", () => {
  it("shows a loading state", () => {
    vi.mocked(entitlementsApi.listMine).mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText("Yuklanmoqda...")).toBeInTheDocument();
  });

  it("renders the user's own entitlements with no admin controls", async () => {
    vi.mocked(entitlementsApi.listMine).mockResolvedValue([ENTITLEMENT]);
    renderPage();
    await waitFor(() => expect(screen.getByText("IELTS")).toBeInTheDocument());
    expect(screen.getByText("Faol")).toBeInTheDocument();
    expect(screen.queryByText("Bekor qilish")).not.toBeInTheDocument();
    expect(screen.queryByText("Cho'zish")).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("shows a friendly empty state when the user has no entitlements", async () => {
    vi.mocked(entitlementsApi.listMine).mockResolvedValue([]);
    renderPage();
    await waitFor(() => expect(screen.getByText(/sizda hozircha mock test ruxsatlari yo'q/i)).toBeInTheDocument());
  });

  it("shows an error state when the fetch fails", async () => {
    vi.mocked(entitlementsApi.listMine).mockRejectedValue(new Error("network error"));
    renderPage();
    await waitFor(() => expect(screen.getByText("Yuklab bo'lmadi")).toBeInTheDocument());
  });
});
