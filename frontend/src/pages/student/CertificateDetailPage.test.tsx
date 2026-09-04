import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CertificateDetailPage } from "./CertificateDetailPage";
import { certificatesApi } from "@/api/certificates";
import { ApiError } from "@/api/client";

vi.mock("@/api/certificates");

function renderDetailPage(certificateId = "c1") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/student/certificates/${certificateId}`]}>
        <Routes>
          <Route path="/student/certificates/:certificateId" element={<CertificateDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("CertificateDetailPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("loads and shows the real certificate number", async () => {
    vi.mocked(certificatesApi.get).mockResolvedValue({
      id: "c1", user_id: "u1", result_id: "r1", template_id: null,
      certificate_number: "CERT-0042", pdf_url: null, status: "issued", created_at: "2026-01-01T00:00:00Z", verification_code: "VC-TEST-0042",
    });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText("CERT-0042")).toBeInTheDocument());
  });

  it("shows the verification_code (backend fix) with a link to the public verify page", async () => {
    vi.mocked(certificatesApi.get).mockResolvedValue({
      id: "c1", user_id: "u1", result_id: "r1", template_id: null,
      certificate_number: "CERT-0042", pdf_url: null, status: "issued", created_at: "2026-01-01T00:00:00Z", verification_code: "VC-TEST-0042",
    });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText("VC-TEST-0042")).toBeInTheDocument());
    const link = screen.getByText("Kodni tekshirish").closest("a");
    expect(link).toHaveAttribute("href", "/certificates/verify?code=VC-TEST-0042");
  });

  it("shows ErrorState on a 404 (not found or not owned)", async () => {
    vi.mocked(certificatesApi.get).mockRejectedValue(new ApiError("Sertifikat topilmadi", null, 404));
    renderDetailPage();
    await waitFor(() => expect(screen.getByText("Sertifikat")).toBeInTheDocument());
  });

  it("NEVER shows a download button — pdf_url is always null in the current backend", async () => {
    vi.mocked(certificatesApi.get).mockResolvedValue({
      id: "c1", user_id: "u1", result_id: "r1", template_id: null,
      certificate_number: "CERT-0042", pdf_url: null, status: "issued", created_at: "2026-01-01T00:00:00Z", verification_code: "VC-TEST-0042",
    });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText("CERT-0042")).toBeInTheDocument());
    expect(screen.queryByText(/yuklab olish/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/download/i)).not.toBeInTheDocument();
  });
});
