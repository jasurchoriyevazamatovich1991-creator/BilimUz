import { describe, expect, it } from "vitest";
import { componentsForProfile, parseTableText, SCORE_COMPONENTS } from "./scaledScoring";

describe("scaledScoring helpers (Task 4)", () => {
  it("parses comma, tab, space and semicolon separated rows and skips blank lines", () => {
    expect(parseTableText("0, 200\n1\t210\n\n2 230\n3;250\n")).toEqual({
      entries: [
        { raw: "0", scaled: "200" }, { raw: "1", scaled: "210" }, { raw: "2", scaled: "230" }, { raw: "3", scaled: "250" },
      ],
    });
  });

  it("keeps decimal values as strings (IELTS half bands)", () => {
    expect(parseTableText("10, 4.5\n12.5, 5")).toEqual({ entries: [{ raw: "10", scaled: "4.5" }, { raw: "12.5", scaled: "5" }] });
  });

  it.each(["0, 200, 3", "abc, 200", "0", "1e3, 200", "0, two"])("names the bad line for %s", (line) => {
    const out = parseTableText(`0, 200\n${line}`);
    expect(out).toEqual({ error: expect.stringContaining("2-qator") });
  });

  it("requires at least one row", () => {
    expect(parseTableText("  \n ")).toEqual({ error: "Kamida bitta qator kiriting" });
  });

  it("lists components per profile and marks examiner-rated ones", () => {
    expect(componentsForProfile("sat")).toEqual(["sat_reading_writing", "sat_math"]);
    expect(componentsForProfile(null)).toEqual([]);
    expect(SCORE_COMPONENTS.ielts_writing.tableConvertible).toBe(false);
    expect(SCORE_COMPONENTS.gre_analytical_writing.tableConvertible).toBe(false);
    expect(SCORE_COMPONENTS.gre_verbal.tableConvertible).toBe(true);
  });
});
