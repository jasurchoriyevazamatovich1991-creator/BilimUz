/**
 * New file — Sprint 36. Every shape verified directly against the real
 * backend app/modules/progress/{schemas,router}.py and the new
 * POST /lessons/{id}/complete endpoint before writing this.
 */
import { httpClient, unwrap } from "./client";

export interface MyProgressOut {
  completed_lessons: number;
  total_lessons: number;
  percentage: number;
  completed_lesson_ids: string[];
}

export interface LessonProgressOut {
  id: string;
  lesson_id: string;
  completed_at: string;
}

export const progressApi = {
  getMyProgress: () => unwrap<MyProgressOut>(httpClient.get("/progress/me")),

  /** Lives on the lessons endpoint (POST /lessons/{id}/complete) —
   * matches the real backend route exactly; completing is an action on
   * a Lesson resource, not a separate "progress" resource. Idempotent
   * on the backend — safe to call more than once. */
  completeLesson: (lessonId: string) =>
    unwrap<LessonProgressOut>(httpClient.post(`/lessons/${lessonId}/complete`)),
};
