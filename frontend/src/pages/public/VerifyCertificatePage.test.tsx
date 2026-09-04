import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { VerifyCertificatePage } from "./VerifyCertificatePage";
import { certificatesApi } from "@/api/certificates";
import { useAuthStore } from "@/store/authStore";

vi.mock("@/api/certificates");

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <VerifyCertificatePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function renderPageWithCode(code: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/certificates/verify?code=${code}`]}>
        <VerifyCertificatePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("VerifyCertificatePage — public, no authentication required", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.getState().logout(); // explicitly logged-out state — this page must still work
  });

  it("renders and accepts input while logged out (no ProtectedRoute involved)", () => {
    renderPage();
    expect(screen.getByLabelText("Tekshiruv kodi")).toBeInTheDocument();
    expect(screen.getByText("Tekshirish")).toBeInTheDocument();
  });

  it("pre-fills and auto-submits from a ?code= query param (the link CertificateDetailPage.tsx generates)", async () => {
    vi.mocked(certificatesApi.verify).mockResolvedValue({
      certificate_number: "CERT-0042", is_valid: true, verified_count: 1,
    });
    renderPageWithCode("VC-TEST-0042");

    await waitFor(() => expect(certificatesApi.verify).toHaveBeenCalledWith("VC-TEST-0042"));
    await waitFor(() => expect(screen.getByText("Sertifikat haqiqiy")).toBeInTheDocument());
    expect(screen.getByLabelText("Tekshiruv kodi")).toHaveValue("VC-TEST-0042");
  });

  it("shows a valid result on success", async () => {
    vi.mocked(certificatesApi.verify).mockResolvedValue({
      certificate_number: "CERT-0001", is_valid: true, verified_count: 3,
    });
    renderPage();
    fireEvent.change(screen.getByLabelText("Tekshiruv kodi"), { target: { value: "abc123" } });
    fireEvent.click(screen.getByText("Tekshirish"));

    await waitFor(() => expect(screen.getByText("Sertifikat haqiqiy")).toBeInTheDocument());
    expect(certificatesApi.verify).toHaveBeenCalledWith("abc123");
  });

  it("shows an invalid result when is_valid is false", async () => {
    vi.mocked(certificatesApi.verify).mockResolvedValue({
      certificate_number: "CERT-0002", is_valid: false, verified_count: 1,
    });
    renderPage();
    fireEvent.change(screen.getByLabelText("Tekshiruv kodi"), { target: { value: "revoked" } });
    fireEvent.click(screen.getByText("Tekshirish"));

    await waitFor(() => expect(screen.getByText("Sertifikat haqiqiy emas")).toBeInTheDocument());
  });

  it("shows an error state for an unknown code (backend 404)", async () => {
    const { ApiError } = await import("@/api/client");
    vi.mocked(certificatesApi.verify).mockRejectedValue(new ApiError("Tekshiruv kodi noto'g'ri", null, 404));
    renderPage();
    fireEvent.change(screen.getByLabelText("Tekshiruv kodi"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByText("Tekshirish"));

    await waitFor(() => expect(screen.getByText("Tekshiruv kodi noto'g'ri")).toBeInTheDocument());
  });

  it("never displays student PII fields — only certificate_number/is_valid/verified_count exist in the response", async () => {
    vi.mocked(certificatesApi.verify).mockResolvedValue({
      certificate_number: "CERT-0003", is_valid: true, verified_count: 1,
    });
    renderPage();
    fireEvent.change(screen.getByLabelText("Tekshiruv kodi"), { target: { value: "abc" } });
    fireEvent.click(screen.getByText("Tekshirish"));
    await waitFor(() => expect(screen.getByText("CERT-0003")).toBeInTheDocument());
    // No name/email/phone fields are ever rendered by this page — the
    // component only reads the three real VerificationResultOut fields.
  });
});
