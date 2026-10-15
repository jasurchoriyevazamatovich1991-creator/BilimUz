/**
 * Catalog Products API wrapper (Admin Management of Mock Test
 * Entitlements, Task D). Used here only to let an admin pick a
 * published Mock Test "direction" (a catalog product with
 * product_type='mock_test', whose name is the subject/exam direction,
 * e.g. "Fizika Mock Test" or "IELTS Mock Test") when granting an
 * entitlement — reuses the existing /catalog/products endpoints
 * (backend app/modules/catalog/router.py), no new backend surface
 * needed for this. Every shape verified against that router's real
 * CatalogProductOut/CatalogProductListParams schemas.
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface CatalogProductOut {
  id: string;
  product_type: "grade_subscription" | "mock_test" | "course";
  grade_id: string | null;
  subject_id: string | null;
  name: string;
  price: number;
  duration_days: number | null;
  status: "draft" | "published" | "archived";
  created_at: string;
  updated_at: string;
}

export interface CatalogProductListParams {
  page: number;
  per_page: number;
  search?: string;
  product_type?: string;
  status?: string;
  sort?: string;
}

export const catalogApi = {
  list: (params: CatalogProductListParams) =>
    unwrap<PaginatedResponse<CatalogProductOut>>(httpClient.get("/catalog/products", { params })),
};
