/** Task 6 — safe calculator parser (no eval). */
import { describe, expect, it } from "vitest";
import { evaluateExpression, formatNumber, MAX_EXPRESSION_LENGTH } from "./calculator";

const value = (e: string) => {
  const r = evaluateExpression(e);
  if (!r.ok) throw new Error(`expected ok for ${e}, got ${r.error}`);
  return r.display;
};
const error = (e: string) => {
  const r = evaluateExpression(e);
  return r.ok ? null : r.error;
};

describe("evaluateExpression", () => {
  it.each([
    ["1+2", "3"], ["7−10", "-3"], ["6×7", "42"], ["8÷4", "2"], ["2+3*4", "14"], ["(2+3)*4", "20"],
    ["10/4", "2.5"], ["0.1+0.2", "0.3"], [".5+.5", "1"], ["2,5*2", "5"], ["-3+5", "2"], ["-(2+3)", "-5"],
    ["2*-3", "-6"], ["--4", "4"], ["((1+2)*(3+4))", "21"], [" 1 + 1 ", "2"], ["1/3", "0.333333333333"], ["0*-5", "0"],
  ])("%s = %s", (expr, expected) => {
    expect(value(expr)).toBe(expected);
  });

  it("reports division by zero instead of Infinity", () => {
    expect(error("5/0")).toBe("divide_by_zero");
    expect(error("1÷(2-2)")).toBe("divide_by_zero");
  });

  it.each(["", "   ", "2+", "*3", "(1+2", "1+2)", "()", "1..2", "1.2.3", ".", "2 3", "abc", "alert(1)", "1;2", "2**3", "1e5", "Math.PI", "constructor"])(
    "rejects invalid input %j",
    (expr) => {
      expect(error(expr)).toBe("invalid");
    },
  );

  it("rejects overly long or deeply nested expressions", () => {
    expect(error("1+".repeat(MAX_EXPRESSION_LENGTH) + "1")).toBe("invalid");
    expect(error("(".repeat(80) + "1" + ")".repeat(80))).toBe("invalid");
  });

  it("handles very large numbers without crashing", () => {
    // The 200-character limit keeps results finite; "overflow" is a
    // defensive fallback only.
    expect(value("9".repeat(99) + "*" + "9".repeat(99))).toBe("1e+198");
  });

  it("never evaluates code", () => {
    const w = globalThis as unknown as { __calcPwned?: boolean };
    evaluateExpression("globalThis.__calcPwned=true");
    expect(w.__calcPwned).toBeUndefined();
  });
});

describe("formatNumber", () => {
  it("normalises -0 and long values", () => {
    expect(formatNumber(-0)).toBe("0");
    expect(formatNumber(1e20)).toBe("1e+20");
    expect(formatNumber(123.456)).toBe("123.456");
  });
});
