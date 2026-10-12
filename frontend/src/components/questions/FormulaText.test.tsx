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

  // --- Sprint 83 — FormulaText rendering safety: a literal `$` inside
  // an HTML tag/attribute must never pair with a `$` elsewhere in the
  // text and corrupt the surrounding markup. The only attribute
  // bleach's own allowlist (backend Sprint 32) ever lets through is
  // `href` on `<a>`, and `$` is an ordinary, unescaped URL character —
  // so this is the realistic, directly-relevant shape of the bug, not
  // a contrived one. ---

  it("does not corrupt an <a href> containing a literal $ when a formula appears later in the text", () => {
    // Before the Sprint 83 fix, the single `$` inside the href paired
    // with the `$` opening the later inline formula, and the regex's
    // lazily-matched span swallowed the attribute's closing quote, the
    // tag's `>`, and the entire `<a>...</a>` element — handing that
    // corrupted fragment to KaTeX in place of real markup.
    const html = '<a href="https://x.com/$cheap">link</a> narxi $5$ so\'m';
    const { container } = render(<FormulaText html={html} />);
    const anchor = container.querySelector("a");
    expect(anchor).toBeInTheDocument();
    expect(anchor?.getAttribute("href")).toBe("https://x.com/$cheap");
    expect(anchor?.textContent).toBe("link");
  });

  it("preserves an href attribute containing a $ even with no formula anywhere else in the text", () => {
    const html = '<a href="https://x.com/$5-off">chegirma</a>';
    const { container } = render(<FormulaText html={html} />);
    const anchor = container.querySelector("a");
    expect(anchor?.getAttribute("href")).toBe("https://x.com/$5-off");
    expect(anchor?.textContent).toBe("chegirma");
  });

  it("still renders a real formula that appears entirely within one text node, alongside an unrelated tag", () => {
    const html = '<b>Natija:</b> $E = mc^2$';
    const { container } = render(<FormulaText html={html} />);
    expect(container.querySelector("b")?.textContent).toBe("Natija:");
    expect(container.querySelector(".katex")).toBeInTheDocument();
  });

  it("renders a block formula alongside HTML tags without disturbing tag structure", () => {
    const html = '<p>Qoida:</p>$$a^2 + b^2 = c^2$$<p>tugadi</p>';
    const { container } = render(<FormulaText html={html} />);
    const paragraphs = container.querySelectorAll("p");
    expect(paragraphs).toHaveLength(2);
    expect(paragraphs[0].textContent).toBe("Qoida:");
    expect(paragraphs[1].textContent).toBe("tugadi");
    expect(container.querySelector(".katex-display")).toBeInTheDocument();
  });

  it("handles empty input without throwing and renders nothing", () => {
    const { container } = render(<FormulaText html="" />);
    expect(container.querySelector("span")?.textContent).toBe("");
  });

  it("leaves a malformed/unclosed $$ block as literal text without crashing", () => {
    const { container } = render(<FormulaText html="Tugallanmagan $$ belgi" />);
    expect(container.textContent).toContain("Tugallanmagan $$ belgi");
  });

  it("treats escaped HTML entities in text as ordinary characters, not formula delimiters", () => {
    // Bleach-sanitized output may contain HTML entities (e.g. &amp;)
    // as literal escaped text — these must pass through untouched
    // and must never be mistaken for `$` delimiters.
    const html = "Narx &amp; chegirma $x+1$";
    const { container } = render(<FormulaText html={html} />);
    expect(container.textContent).toContain("Narx & chegirma");
    expect(container.querySelector(".katex")).toBeInTheDocument();
  });

  it("renders mixed text, multiple formulas, and multiple HTML tags together correctly", () => {
    const html = '<p>Birinchi $a=1$ va <b>ikkinchi</b> $$b=2$$ natija.</p>';
    const { container } = render(<FormulaText html={html} />);
    expect(container.querySelector("p")).toBeInTheDocument();
    expect(container.querySelector("b")?.textContent).toBe("ikkinchi");
    expect(container.querySelectorAll(".katex")).toHaveLength(2);
    expect(container.querySelectorAll(".katex-display")).toHaveLength(1);
  });

  it("preserves a self-closing tag with a $ in one of its attributes (existing img allowlist shape)", () => {
    // Even though the current backend allowlist (RICH_TEXT_ALLOWED_ATTRIBUTES)
    // only grants `href` on `<a>` today, FormulaText's own tag-boundary
    // split is attribute-agnostic by design — it must hold for ANY
    // attribute value on ANY tag, not just the one case currently
    // allowed through, since the regex itself has no allowlist
    // awareness and must not depend on the backend's current policy.
    const html = '<img src="pic.png?x=$5" alt="rasm" />Narx: $10$';
    const { container } = render(<FormulaText html={html} />);
    const img = container.querySelector("img");
    expect(img?.getAttribute("src")).toBe("pic.png?x=$5");
    expect(img?.getAttribute("alt")).toBe("rasm");
    expect(container.querySelector(".katex")).toBeInTheDocument();
  });
});
