/**
 * Admin Management of Mock Test Entitlements, Task D — spec §7.11
 * ("admin UI handles loading, success, errors, and revocation
 * confirmation"). API layer mocked, same pattern as
 * pages/admin/TestFormPage.test.tsx.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { UserEntitlementsPanel } from "./UserEntitlementsPanel";
import { entitlementsApi, type EntitlementOut } from "@/api/entitlements";
import { catalogApi } from "@/api/catalog";

vi.mock("@/api/entitlements");
vi.mock("@/api/catalog");

const EMPTY_PRODUCTS = { items: [], meta: { page: 1, per_page: 100, total: 0, total_pages: 0 } };

function renderPanel(userId = "user-1") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <UserEntitlementsPanel userId={userId} />
    </QueryClientProvider>,
  );
}

function makeEntitlement(overrides: Partial<EntitlementOut> = {}): EntitlementOut {
  return {
    id: "e1", user_id: "user-1", product_id: "p1", source: "admin_grant",
    granted_by: "admin-1", payment_id: null, status: "active",
    start_date: "2026-01-01T00:00:00Z", end_date: "2026-12-31T00:00:00Z", reason: null,
    created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
    product_name: "Fizika Mock Test", product_type: "mock_test",
    subject_id: "s1", subject_name: "Fizika", granted_by_name: "Admin Adminov",
    effective_status: "active",
    ...overrides,
  };
}

describe("UserEntitlementsPanel", () => {
  beforeEach(() => {
    vi.mocked(catalogApi.list).mockResolvedValue({
      items: [{ id: "p1", product_type: "mock_test", grade_id: null, subject_id: "s1", name: "Fizika Mock Test", price: 0, duration_days: null, status: "published", created_at: "", updated_at: "" }],
      meta: { page: 1, per_page: 100, total: 1, total_pages: 1 },
    });
  });

  it("shows a loading state while entitlements are being fetched", async () => {
    vi.mocked(entitlementsApi.listForUser).mockReturnValue(new Promise(() => {}));
    renderPanel();
    expect(screen.getByText("Yuklanmoqda...")).toBeInTheDocument();
  });

  it("shows an error state when the fetch fails", async () => {
    vi.mocked(entitlementsApi.listForUser).mockRejectedValue(new Error("network error"));
    renderPanel();
    await waitFor(() => expect(screen.getByText(/yuklab bo'lmadi/i)).toBeInTheDocument());
  });

  it("renders an empty state when the user has no entitlements yet", async () => {
    vi.mocked(entitlementsApi.listForUser).mockResolvedValue([]);
    renderPanel();
    await waitFor(() => expect(screen.getByText(/hozircha Mock Test ruxsatlari yo'q/i)).toBeInTheDocument());
  });

  it("lists an existing entitlement with its subject, status, and granting admin", async () => {
    vi.mocked(entitlementsApi.listForUser).mockResolvedValue([makeEntitlement()]);
    renderPanel();
    await waitFor(() => expect(screen.getByText("Fizika")).toBeInTheDocument());
    expect(screen.getByText("Faol")).toBeInTheDocument();
    expect(screen.getByText("Admin Adminov")).toBeInTheDocument();
  });

  it("only shows Revoke for an active/scheduled entitlement, not an already-revoked one", async () => {
    vi.mocked(entitlementsApi.listForUser).mockResolvedValue([makeEntitlement({ status: "revoked", effective_status: "revoked" })]);
    renderPanel();
    await waitFor(() => expect(screen.getByText("Fizika")).toBeInTheDocument());
    expect(screen.queryByText("Bekor qilish")).not.toBeInTheDocument();
  });

  it("asks for confirmation before revoking, and only calls the API after confirming", async () => {
    const user = userEvent.setup();
    vi.mocked(entitlementsApi.listForUser).mockResolvedValue([makeEntitlement()]);
    vi.mocked(entitlementsApi.revoke).mockResolvedValue(makeEntitlement({ status: "revoked", effective_status: "revoked" }));
    renderPanel();
    await waitFor(() => expect(screen.getByText("Fizika")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "Bekor qilish" }));
    expect(entitlementsApi.revoke).not.toHaveBeenCalled();

    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(/orqaga qaytarib bo'lmaydi/i)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Ha, bekor qilish" }));

    await waitFor(() => expect(entitlementsApi.revoke).toHaveBeenCalledWith("e1", undefined));
  });

  it("grants a new entitlement by selecting a published direction and submitting", async () => {
    const user = userEvent.setup();
    vi.mocked(entitlementsApi.listForUser).mockResolvedValue([]);
    vi.mocked(entitlementsApi.grant).mockResolvedValue(makeEntitlement());
    renderPanel();
    await waitFor(() => expect(screen.getByLabelText("Fan / yo'nalish")).toBeInTheDocument());

    await user.selectOptions(screen.getByLabelText("Fan / yo'nalish"), "p1");
    await user.click(screen.getByRole("button", { name: "Ruxsat berish" }));

    await waitFor(() =>
      expect(entitlementsApi.grant).toHaveBeenCalledWith(
        expect.objectContaining({ user_id: "user-1", product_id: "p1", duration_days: 30 }),
      ),
    );
  });

  it("does not show a direction picker option when no published Mock Test product exists", async () => {
    vi.mocked(catalogApi.list).mockResolvedValue(EMPTY_PRODUCTS);
    vi.mocked(entitlementsApi.listForUser).mockResolvedValue([]);
    renderPanel();
    await waitFor(() => expect(screen.getByText(/avval Katalog bo'limida yarating/i)).toBeInTheDocument());
  });
});
