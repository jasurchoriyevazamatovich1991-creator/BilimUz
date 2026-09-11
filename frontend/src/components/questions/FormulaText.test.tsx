import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { FormulaText } from "./FormulaText";

describe("FormulaText", () => {
  it("renders plain HTML with no formula unchanged", () => {
    const { container } = render(<FormulaText html="<b>Salom</b>" />);
    expect(container.querySelector("b")?.textContent).toBe("Salom");
  });

  it("renders a $...$ formula segment via KaTeX", () => {
    const { container } = render(<FormulaText html="Formula: $F = ma$" />);
    expect(container.querySelector(".katex")).toBeInTheDocument();
  });

  it("leaves malformed/unclosed $ as literal text without crashing", () => {
    const { container } = render(<FormulaText html="Yakunlanmagan $ belgisi" />);
    expect(container.textContent).toContain("Yakunlanmagan $ belgisi");
  });

  it("renders multiple formulas in the same text", () => {
    const { container } = render(<FormulaText html="$a=1$ va $b=2$" />);
    expect(container.querySelectorAll(".katex").length).toBe(2);
  });
});
