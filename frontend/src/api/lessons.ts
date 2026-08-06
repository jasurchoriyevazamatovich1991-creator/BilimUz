/** Minimal wrapper for the lessons-count widget (GET /lessons, public
 * — verified against backend/app/modules/lessons/router.py). */
import { httpClient, unwrap } from "./client";
import type { PaginatedResponse } from "@/types/pagination";

export interface LessonOut {
  id: string;
  title: string;
}

export const lessonsApi = {
  count: async (): Promise<number> => {
    const result = await unwrap<PaginatedResponse<LessonOut>>(httpClient.get("/lessons", { params: { per_page: 1 } }));
    return result.meta.total;
  },
};
