/** Minimal wrapper for the my-certificates-count widget
 * (GET /certificates/me, authenticated — verified against
 * backend/app/modules/certificates/router.py). */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface CertificateOut {
  id: string;
  certificate_number: string;
  status: string;
}

export const certificatesApi = {
  myCount: async (): Promise<number> => {
    const result = await unwrap<PaginatedResponse<CertificateOut>>(
      httpClient.get("/certificates/me", { params: { per_page: 1 } }),
    );
    return result.meta.total;
  },
};
