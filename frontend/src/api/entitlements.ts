/**
 * Mock Test Entitlements API wrapper (Admin Management of Mock Test
 * Entitlements, Task D). Every shape verified against the real backend
 * app/modules/entitlements/{schemas,router}.py before writing.
 *
 * Grant/extend accept EITHER end_date OR duration_days, never both —
 * mirrors EntitlementGrantRequest/EntitlementExtendRequest's own
 * model_validator on the backend (sending both is a 422, not silently
 * resolved client-side).
 */
import { httpClient, unwrap } from "./client";

export interface EntitlementOut {
  id: string;
  user_id: string;
  product_id: string;
  source: "purchase" | "admin_grant";
  granted_by: string | null;
  payment_id: string | null;
  status: "active" | "expired" | "revoked";
  start_date: string;
  end_date: string | null;
  reason: string | null;
  created_at: string;
  updated_at: string;
  product_name: string;
  product_type: "grade_subscription" | "mock_test" | "course";
  subject_id: string | null;
  subject_name: string | null;
  granted_by_name: string | null;
  /** Computed server-side — "active" | "scheduled" | "expired" | "revoked".
   * Never compute this client-side (see parent docstring + backend
   * README's "avoid frontend-only expiration checks" note). */
  effective_status: "active" | "scheduled" | "expired" | "revoked";
}

export interface EntitlementGrantRequest {
  user_id: string;
  product_id: string;
  start_date?: string;
  end_date?: string;
  duration_days?: number;
  reason?: string;
}

export interface EntitlementExtendRequest {
  end_date?: string;
  duration_days?: number;
  reason?: string;
}

export interface EntitlementRevokeRequest {
  reason?: string;
}

export const entitlementsApi = {
  grant: (data: EntitlementGrantRequest) => unwrap<EntitlementOut>(httpClient.post("/entitlements/admin/grant", data)),

  extend: (entitlementId: string, data: EntitlementExtendRequest) =>
    unwrap<EntitlementOut>(httpClient.post(`/entitlements/admin/${entitlementId}/extend`, data)),

  revoke: (entitlementId: string, data: EntitlementRevokeRequest = {}) =>
    unwrap<EntitlementOut>(httpClient.post(`/entitlements/admin/${entitlementId}/revoke`, data)),

  listForUser: (userId: string) => unwrap<EntitlementOut[]>(httpClient.get(`/entitlements/admin/users/${userId}`)),

  listMine: () => unwrap<EntitlementOut[]>(httpClient.get("/entitlements/me")),
};
