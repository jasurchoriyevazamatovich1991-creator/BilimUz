import { describe, expect, it } from "vitest";
import {
  EMPTY_GRADING,
  gradingPayload,
  gradingStateFromQuestion,
  isValidNumericAnswer,
  validateGradingState,
} from "./shortAnswerGrading";

describe("shortAnswerGrading helpers (Task 2)", () => {
  it.each(["12", "-3", "+4", "3.25", ".5", "5.", "7/2", "-7/2", "−2"])("accepts numeric %s", (v) => {
    expect(isValidNumericAnswer(v)).toBe(true);
  });

  it.each(["", "abc", "1,5", "1e3", "1 000", "3/0", "3.5/2", "1".repeat(41)])("rejects numeric %s", (v) => {
    expect(isValidNumericAnswer(v)).toBe(false);
  });

  it("manual-review state is always valid and sends explicit nulls", () => {
    expect(validateGradingState(EMPTY_GRADING)).toBeNull();
    expect(gradingPayload(EMPTY_GRADING)).toEqual({
      answer_format: null, accepted_answers: null, case_sensitive: false, numeric_tolerance: null,
    });
  });

  it("requires at least one non-blank accepted answer", () => {
    expect(validateGradingState({ ...EMPTY_GRADING, format: "text", acceptedAnswers: ["  ", ""] })).toMatch(/Kamida bitta/);
  });

  it("text payload trims, drops blanks, keeps case flag and never sends tolerance", () => {
    const state = { format: "text" as const, acceptedAnswers: [" library ", "", "the library"], caseSensitive: true, tolerance: "0.5" };
    expect(validateGradingState(state)).toBeNull();
    expect(gradingPayload(state)).toEqual({
      answer_format: "text", accepted_answers: ["library", "the library"], case_sensitive: true, numeric_tolerance: null,
    });
  });

  it("numeric payload sends tolerance as a string and forces case_sensitive false", () => {
    const state = { format: "numeric" as const, acceptedAnswers: ["2/3", "0.667"], caseSensitive: true, tolerance: " 0.001 " };
    expect(gradingPayload(state)).toEqual({
      answer_format: "numeric", accepted_answers: ["2/3", "0.667"], case_sensitive: false, numeric_tolerance: "0.001",
    });
  });

  it("numeric validation names the bad value and rejects a negative tolerance", () => {
    expect(validateGradingState({ format: "numeric", acceptedAnswers: ["1,5"], caseSensitive: false, tolerance: "" })).toMatch(/'1,5'/);
    expect(validateGradingState({ format: "numeric", acceptedAnswers: ["1"], caseSensitive: false, tolerance: "-1" })).toMatch(/Tolerance/);
    expect(validateGradingState({ format: "numeric", acceptedAnswers: ["1"], caseSensitive: false, tolerance: "abc" })).toMatch(/Tolerance/);
  });

  it("loads an existing question's configuration", () => {
    expect(gradingStateFromQuestion({ answer_format: "numeric", accepted_answers: ["12"], case_sensitive: false, numeric_tolerance: "0.5" }))
      .toEqual({ format: "numeric", acceptedAnswers: ["12"], caseSensitive: false, tolerance: "0.5" });
    expect(gradingStateFromQuestion({ answer_format: null, accepted_answers: null })).toEqual(EMPTY_GRADING);
  });
});
