/**
 * Catalog Products data hooks — read-only here, just enough to list
 * published Mock Test "directions" for the entitlement-grant picker
 * (Admin Management of Mock Test Entitlements, Task D). Same
 * toast-on-error shape as hooks/useSubjects.ts.
 */
import { useEffect } from "react";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { catalogApi, type CatalogProductListParams } from "@/api/catalog";
import { useToastStore } from "@/store/toastStore";
import { ApiError } from "@/api/client";

function useToastOnQueryError(query: UseQueryResult<unknown, unknown>) {
  const addToast = useToastStore((s) => s.addToast);
  useEffect(() => {
    if (query.isError) {
      addToast(query.error instanceof ApiError ? query.error.message : "Ma'lumot yuklanmadi");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.isError, query.error]);
}

export function useCatalogProductsList(params: CatalogProductListParams) {
  const query = useQuery({ queryKey: ["catalog-products", "list", params], queryFn: () => catalogApi.list(params) });
  useToastOnQueryError(query);
  return query;
}

/** Published Mock Test products only — the exact set of "directions"
 * (Fizika, Matematika, IELTS, SAT, GRE, ...) an admin can grant access
 * to, per spec §2.3's "using the directions actually supported by the
 * existing catalog." */
export function usePublishedMockTestProducts() {
  return useCatalogProductsList({ page: 1, per_page: 100, product_type: "mock_test", status: "published" });
}
