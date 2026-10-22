/** Task 7 — provenance labels and range helpers. */
import { describe, expect, it } from "vitest";
import {
  SAT_PRACTICE_FORMS, SCORE_BASIS_LABELS, formatScoreRange, parseRangeTableText, scoreBasisExplanation, type ScoreBasis,
} from "./scaledScoring";

describe("formatScoreRange", () => {
  it("shows a range only when the ends differ", () => {
    expect(formatScoreRange(null, 6, 6.5)).toBe("6–6.5");
    expect(formatScoreRange(510, 510, 510)).toBe("510");
    expect(formatScoreRange(600, null, null)).toBe("600");
    expect(formatScoreRange(null, null, null)).toBeNull();
  });
});

describe("parseRangeTableText", () => {
  it("parses raw, lower, upper rows", () => {
    expect(parseRangeTableText("0, 200, 200\n\n1\t200\t210")).toEqual({
      entries: [{ raw: "0", lower: "200", upper: "200" }, { raw: "1", lower: "200", upper: "210" }],
    });
  });
  it("names the bad line", () => {
    expect(parseRangeTableText("0, 200, 200\n1, 210")).toEqual({ error: expect.stringContaining("2-qator") });
    expect(parseRangeTableText("")).toEqual({ error: "Kamida bitta qator kiriting" });
  });
});

describe("score basis wording", () => {
  it("never presents any basis as an official exam result", () => {
    const bases = Object.keys(SCORE_BASIS_LABELS) as ScoreBasis[];
    for (const b of bases) {
      for (const profile of ["ielts", "sat", "gre", null]) {
        expect(scoreBasisExplanation(b, profile)).toMatch(/natija(si)? emas/);
      }
    }
    expect(scoreBasisExplanation("official_practice_test", "sat")).toContain("nonadaptive");
  });

  it("lists exactly SAT Practice Tests 4–11", () => {
    expect(SAT_PRACTICE_FORMS.map((f) => f.id)).toEqual([4, 5, 6, 7, 8, 9, 10, 11].map((n) => `sat_practice_test_${n}`));
  });
});

describe("Task 8 — scale mismatch wording", () => {
  it("explains the mismatch for both IELTS and SAT practice tables", async () => {
    const { SCALED_STATUS_LABELS } = await import("./scaledScoring");
    expect(SCALED_STATUS_LABELS.raw_scale_mismatch).toMatch(/IELTS: 40 ta bir ballik/);
    expect(SCALED_STATUS_LABELS.raw_scale_mismatch).toMatch(/SAT: jadvaldagi eng katta xom ball/);
  });
});

describe("Task 9 — estimate wording follows the actual source", () => {
  it("names IELTS.org only for the IELTS.org indicative source", async () => {
    const { scoreBasisExplanation, isIeltsIndicativeSource, practiceDisclaimer } = await import("./scaledScoring");
    expect(isIeltsIndicativeSource("https://www.ielts.org/take-a-test/your-results/ielts-scoring-in-detail")).toBe(true);
    expect(isIeltsIndicativeSource("https://example.com/ielts.org/")).toBe(false);
    expect(isIeltsIndicativeSource(null)).toBe(false);
    expect(scoreBasisExplanation("estimate", "ielts", { sourceUrl: "https://www.ielts.org/x" })).toContain("IELTS.org");
    expect(scoreBasisExplanation("estimate", "ielts")).not.toContain("IELTS.org");
    expect(scoreBasisExplanation("estimate", "ielts", { overall: true })).not.toContain("IELTS.org");
    for (const p of ["ielts", "sat", "gre"]) {
      expect(scoreBasisExplanation("estimate", p, { overall: true })).toMatch(/natija(si)? emas/);
      expect(practiceDisclaimer(p)).toMatch(/rasmiy .* natijasi emas/);
    }
  });
});
