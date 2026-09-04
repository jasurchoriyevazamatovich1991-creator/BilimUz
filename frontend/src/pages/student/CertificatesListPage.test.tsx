import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CertificatesListPage } from "./CertificatesListPage";
import { certificatesApi } from "@/api/certificates";

vi.mock("@/api/certificates");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <CertificatesListPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const MOCK_CERT = {
  id: "c1", user_id: "u1", result_id: "r1", template_id: null,
  certificate_number: "CERT-0001", pdf_url: null, status: "issued", created_at: "2026-01-01T00:00:00Z", verification_code: "VC-TEST-0001",
};

describe("CertificatesListPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("loads and shows a certificate row on success", async () => {
    vi.mocked(certificatesApi.listMine).mockResolvedValue({
      items: [MOCK_CERT], meta: { page: 1, per_page: 20, total: 1, total_pages: 1 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("CERT-0001")).toBeInTheDocument());
  });

  it("shows an explanatory empty state when there are no certificates", async () => {
    vi.mocked(certificatesApi.listMine).mockResolvedValue({
      items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Sizda hali sertifikat yo'q.")).toBeInTheDocument());
  });

  it("shows ErrorState on API failure", async () => {
    vi.mocked(certificatesApi.listMine).mockRejectedValue(new Error("network error"));
    renderPage();
    await waitFor(() => expect(screen.getByText("Sertifikatlarim")).toBeInTheDocument());
  });
});
