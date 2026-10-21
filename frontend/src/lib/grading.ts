/** Task 5 — labels and small helpers for the grading UI. The backend
 * re-validates every score; these checks only give instant feedback. */
import type { ManualComponent, QueueStatus, RubricCriterion } from "@/api/grading";

export const MANUAL_COMPONENT_LABELS: Record<ManualComponent, string> = {
  ielts_writing: "IELTS Writing",
  ielts_speaking: "IELTS Speaking",
  gre_analytical_writing: "GRE Analytical Writing",
};

export const QUEUE_STATUS_LABELS: Record<QueueStatus, string> = {
  pending: "Baholanmagan",
  draft: "Qoralama",
  finalized: "Yakunlangan",
};

export const REVIEW_STATUS_LABELS: Record<string, string> = {
  draft: "Qoralama",
  finalized: "Yakuniy",
  superseded: "Almashtirilgan",
};

/** Returns an error message, or null when the value fits the criterion. */
export function criterionError(c: RubricCriterion, value: string): string | null {
  if (value.trim() === "") return null;
  const n = Number(value);
  const min = Number(c.min);
  const max = Number(c.max);
  const step = Number(c.step);
  if (!Number.isFinite(n)) return `${c.label}: son kiriting`;
  if (n < min || n > max) return `${c.label}: ${c.min}–${c.max} oralig'ida`;
  const steps = (n - min) / step;
  if (Math.abs(steps - Math.round(steps)) > 1e-9) return `${c.label}: ${c.step} qadamli`;
  return null;
}
