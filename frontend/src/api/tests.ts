/**
 * Minimal wrapper for the published-tests-count widget (GET /tests,
 * public — verified against backend/app/modules/tests/router.py). Used
 * by both Admin and Teacher dashboards, since neither has a way to
 * filter to "my own tests" via this endpoint (no owner/created_by
 * filter param exists) — see Sprint 14 implementation notes in
 * frontend/README.md for the full investigation.
 */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface TestOut {
  id: string;
  title: string;
  status: string;
}

export const testsApi = {
  publishedCount: async (): Promise<number> => {
    const result = await unwrap<PaginatedResponse<TestOut>>(
      httpClient.get("/tests", { params: { per_page: 1, status: "published" } }),
    );
    return result.meta.total;
  },
};
