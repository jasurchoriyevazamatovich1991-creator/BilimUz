import { describe, expect, it } from "vitest";
import { criterionError } from "./grading";

const C = { key: "task", label: "Task", min: "0", max: "9", step: "0.5", weight: "1" };

describe("criterionError (Task 5)", () => {
  it("accepts empty (draft) and on-step values", () => {
    expect(criterionError(C, "")).toBeNull();
    expect(criterionError(C, "6.5")).toBeNull();
    expect(criterionError(C, "9")).toBeNull();
  });
  it.each([["10", "oralig'ida"], ["-1", "oralig'ida"], ["6.25", "qadamli"], ["abc", "son kiriting"]])("rejects %s", (v, msg) => {
    expect(criterionError(C, v)).toContain(msg);
  });
});
