/**
 * Minimal wrapper for the recommendations widget (GET /ai/recommendations/me,
 * authenticated — verified against backend/app/modules/ai/router.py).
 * NOTE: expected to legitimately return an empty list — the `ai` module's
 * own README confirms nothing generates a recommendation yet (no real
 * AI provider exists this platform-wide). An empty widget here is
 * correct behavior, not a bug.
 */
import { httpClient, unwrap } from "./client";

export interface RecommendationOut {
  id: string;
  text: string;
}

export const aiApi = {
  myRecommendations: () => unwrap<RecommendationOut[]>(httpClient.get("/ai/recommendations/me")),
};
