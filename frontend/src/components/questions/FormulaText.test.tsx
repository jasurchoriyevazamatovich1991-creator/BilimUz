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

  // --- Sprint 80 — block/display-mode LaTeX ($$...$$) ---

  it("renders a $$...$$ block formula via KaTeX in display mode", () => {
    const { container } = render(<FormulaText html="$$v^2 = v_0^2 + 2as$$" />);
    const katexEl = container.querySelector(".katex-display");
    expect(katexEl).toBeInTheDocument();
  });

  it("renders inline $...$ in non-display mode (no .katex-display wrapper)", () => {
    const { container } = render(<FormulaText html="$F = ma$" />);
    expect(container.querySelector(".katex")).toBeInTheDocument();
    expect(container.querySelector(".katex-display")).not.toBeInTheDocument();
  });

  it("renders both a block and an inline formula in the same text, each in its own mode", () => {
    const { container } = render(<FormulaText html="Inline $a=1$ keyin block $$E = mc^2$$" />);
    expect(container.querySelectorAll(".katex").length).toBe(2);
    expect(container.querySelectorAll(".katex-display").length).toBe(1);
  });

  it("does not mis-split a $$...$$ block into two bogus inline $...$ segments", () => {
    const { container } = render(<FormulaText html="$$a + b$$" />);
    // Exactly one formula rendered (the block), not two inline ones from
    // greedily matching the outer $ pairs as two separate $...$ segments.
    expect(container.querySelectorAll(".katex").length).toBe(1);
  });

  // --- Sprint 80 — security: FormulaText must never execute script-like
  // content smuggled into an already-sanitized HTML string, and KaTeX's
  // own output must not introduce new unsafe markup. ---

  it("does not execute a <script> tag embedded in the html prop", () => {
    // A <script> element inserted via innerHTML/dangerouslySetInnerHTML
    // is parsed into the DOM (browsers and jsdom both do this) but is
    // never EXECUTED that way — this is a browser-spec guarantee, not
    // something FormulaText itself has to implement. What matters is
    // that it never runs.
    render(<FormulaText html="<script>window.__xss = true</script>Salom" />);
    expect((window as unknown as { __xss?: boolean }).__xss).toBeUndefined();
  });

  it("never introduces a javascript: href on top of already-sanitized input", () => {
    // Bleach (backend, Sprint 32) is the real sanitization boundary —
    // its own test_javascript_protocol_link_is_stripped confirms a
    // javascript: href never survives past the backend, leaving an
    // anchor with the tag kept but the href attribute removed. This
    // asserts FormulaText doesn't re-introduce a dangerous href for
    // that already-sanitized shape.
    const { container } = render(<FormulaText html="<a>link</a>" />);
    const anchor = container.querySelector("a");
    expect(anchor).toBeInTheDocument();
    expect(anchor?.getAttribute("href")).toBeNull();
  });

  it("renders an inline event-handler attribute as inert markup, not executed on mount", () => {
    // dangerouslySetInnerHTML never itself evaluates attribute-based
    // event handlers at parse time (no JS runs just from the HTML being
    // inserted) — the real defense against this ever reaching the DOM at
    // all is the backend's bleach allowlist (Sprint 32), verified
    // separately in the backend test suite (validators.py strips
    // on*/script/iframe entirely). This only asserts FormulaText's own
    // mount doesn't trigger anything synchronously.
    expect(() => render(<FormulaText html='<img src="x" onerror="window.__xss2 = true" />' />)).not.toThrow();
    expect((window as unknown as { __xss2?: boolean }).__xss2).toBeUndefined();
  });
});
