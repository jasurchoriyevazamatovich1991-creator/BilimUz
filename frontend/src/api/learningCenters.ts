/** Minimal wrapper for the learning-centers-count widget
 * (GET /learning-centers, public — verified against
 * backend/app/modules/learning_centers/router.py). */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface LearningCenterOut {
  id: string;
  name: string;
}

export const learningCentersApi = {
  count: async (): Promise<number> => {
    const result = await unwrap<PaginatedResponse<LearningCenterOut>>(
      httpClient.get("/learning-centers", { params: { per_page: 1 } }),
    );
    return result.meta.total;
  },
};
