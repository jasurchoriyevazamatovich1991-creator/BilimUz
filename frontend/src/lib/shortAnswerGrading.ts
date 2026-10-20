/**
 * Task 2 — admin-side helpers for short_answer automatic grading.
 *
 * The backend (questions/answer_matching.py) is the authority: it
 * re-validates everything and answers 422 on a bad configuration. These
 * checks only give the admin an immediate, specific message before the
 * request, using the same numeric rules.
 */
import type { QuestionOut, ShortAnswerFormat, ShortAnswerGradingPayload } from "@/api/questions";

export interface ShortAnswerGradingState {
  /** "" = not auto-graded (manual review). */
  format: "" | ShortAnswerFormat;
  acceptedAnswers: string[];
  caseSensitive: boolean;
  tolerance: string;
}

export const EMPTY_GRADING: ShortAnswerGradingState = { format: "", acceptedAnswers: [""], caseSensitive: false, tolerance: "" };

export const MAX_ACCEPTED_ANSWERS = 20;

const DECIMAL = /^[+-]?(\d+(\.\d*)?|\.\d+)$/;
const FRACTION = /^[+-]?\d+\/\d+$/;

/** Mirrors answer_matching.parse_number's accepted shapes (UX only). */
export function isValidNumericAnswer(value: string): boolean {
  const v = value.trim().replace("−", "-");
  if (!v || v.length > 40) return false;
  if (DECIMAL.test(v)) return true;
  if (FRACTION.test(v)) return !/\/0+$/.test(v);
  return false;
}

export function gradingStateFromQuestion(q: Pick<QuestionOut, "answer_format" | "accepted_answers" | "case_sensitive" | "numeric_tolerance">): ShortAnswerGradingState {
  if (!q.answer_format) return { ...EMPTY_GRADING };
  return {
    format: q.answer_format,
    acceptedAnswers: q.accepted_answers && q.accepted_answers.length > 0 ? [...q.accepted_answers] : [""],
    caseSensitive: Boolean(q.case_sensitive),
    tolerance: q.numeric_tolerance ?? "",
  };
}

/** Returns an error message, or null when the state can be sent. */
export function validateGradingState(state: ShortAnswerGradingState): string | null {
  if (!state.format) return null;
  const answers = state.acceptedAnswers.map((a) => a.trim()).filter((a) => a.length > 0);
  if (answers.length === 0) return "Kamida bitta to'g'ri javob kiriting";
  if (answers.length > MAX_ACCEPTED_ANSWERS) return `To'g'ri javoblar soni ${MAX_ACCEPTED_ANSWERS} tadan oshmasligi kerak`;
  if (answers.some((a) => a.length > 255)) return "To'g'ri javob 255 belgidan oshmasligi kerak";
  if (state.format === "numeric") {
    const bad = answers.find((a) => !isValidNumericAnswer(a));
    if (bad !== undefined) return `'${bad}' — son emas. Masalan: 12, 3.5, -0.25 yoki 7/2 (vergulsiz).`;
    const tol = state.tolerance.trim();
    if (tol && !(DECIMAL.test(tol) && !tol.startsWith("-"))) return "Tolerance manfiy bo'lmagan o'nli son bo'lishi kerak (masalan, 0.01)";
  }
  return null;
}

/** The request fields for a short_answer question. "" format sends
 * explicit nulls so an edit can switch a question back to manual review. */
export function gradingPayload(state: ShortAnswerGradingState): ShortAnswerGradingPayload {
  if (!state.format) {
    return { answer_format: null, accepted_answers: null, case_sensitive: false, numeric_tolerance: null };
  }
  const answers = state.acceptedAnswers.map((a) => a.trim()).filter((a) => a.length > 0);
  if (state.format === "text") {
    return { answer_format: "text", accepted_answers: answers, case_sensitive: state.caseSensitive, numeric_tolerance: null };
  }
  const tol = state.tolerance.trim();
  return { answer_format: "numeric", accepted_answers: answers, case_sensitive: false, numeric_tolerance: tol ? tol : null };
}
