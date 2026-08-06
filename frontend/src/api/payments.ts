/**
 * Minimal wrapper for the Super Admin "Payments" widget. IMPORTANT:
 * there is no admin-wide payments/transactions list endpoint in the
 * backend (verified — only GET /payments/me [own history] and
 * GET /payments/plans [public catalog] exist). This wrapper exposes
 * the PLANS catalog count, not actual payment/transaction volume — the
 * dashboard widget is labeled "To'lov rejalari" (Payment Plans), not
 * "To'lovlar", to avoid implying data that doesn't exist. See
 * frontend/README.md's Sprint 15 notes for the full investigation.
 */
import { httpClient, unwrap } from "./client";

export interface PlanOut {
  id: string;
  name: string;
  price: number;
  status: string;
}

export const paymentsApi = {
  activePlansCount: async (): Promise<number> => {
    const plans = await unwrap<PlanOut[]>(httpClient.get("/payments/plans"));
    return plans.length;
  },
};
