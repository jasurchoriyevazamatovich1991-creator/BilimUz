/**
 * Certificates API wrapper. `myCount()` (Sprint 14) unchanged below —
 * extended, not replaced. Every shape verified directly against real
 * backend app/modules/certificates/{schemas,service,router}.py before
 * writing.
 *
 * BACKEND GAP FIXED (see docs/Sprint21_Student_Certificates_UI.md):
 * CertificateOut now includes `verification_code`, attached at the
 * service layer from the separate CertificateVerification record (no
 * DB column added, no migration — verified directly in the backend's
 * updated schemas.py/service.py before writing this file). This is
 * what powers the "Tekshirish kodi" shown on CertificateDetailPage.tsx
 * and used by the public VerifyCertificatePage.tsx.
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface CertificateOut {
  id: string;
  user_id: string;
  result_id: string;
  template_id: string | null;
  certificate_number: string;
  /** Always null in the current backend — PDF export is a future
   * sprint (verified in issue_certificate's own docstring). */
  pdf_url: string | null;
  status: string;
  created_at: string;
  /** The code needed for GET /certificates/verify/{code} — attached
   * server-side from the separate CertificateVerification record, not
   * a real `certificates` table column. */
  verification_code: string;
}

export interface IssueCertificateRequest {
  result_id: string;
  template_id?: string;
}

export interface VerificationResultOut {
  certificate_number: string;
  is_valid: boolean;
  verified_count: number;
}

export const certificatesApi = {
  myCount: async (): Promise<number> => {
    const result = await unwrap<PaginatedResponse<CertificateOut>>(
      httpClient.get("/certificates/me", { params: { per_page: 1 } }),
    );
    return result.meta.total;
  },

  listMine: (params: { page: number; per_page: number }) =>
    unwrap<PaginatedResponse<CertificateOut>>(httpClient.get("/certificates/me", { params })),

  get: (certificateId: string) => unwrap<CertificateOut>(httpClient.get(`/certificates/${certificateId}`)),

  /** Idempotent on (user_id, test_id) — calling this again for an
   * already-certified passing result returns the existing certificate,
   * not an error (verified directly in service.py::issue()). */
  issue: (data: IssueCertificateRequest) => unwrap<CertificateOut>(httpClient.post("/certificates", data)),

  /** Public — no Authorization header needed, works even for a logged-out visitor. */
  verify: (code: string) => unwrap<VerificationResultOut>(httpClient.get(`/certificates/verify/${code}`)),
};
