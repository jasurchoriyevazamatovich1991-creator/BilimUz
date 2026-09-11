/**
 * Sprint 33 — renders `$...$`-delimited LaTeX segments within
 * question/option text via KaTeX; everything outside `$...$` is
 * treated as the ALREADY backend-sanitized HTML from Sprint 32's
 * bleach pipeline. `dangerouslySetInnerHTML` is used only for that
 * backend-sanitized segment (never for anything user-typed at this
 * component's own boundary) — matches the explicit "existing
 * sanitization contract, don't render raw unsafe HTML" requirement.
 */
import { useMemo } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";

interface FormulaTextProps {
  /** Backend-sanitized HTML (question_text/option_text/explanation as
   * returned by the API) — may contain `$...$` LaTeX segments as plain
   * text within it. */
  html: string;
  className?: string;
}

/** Splits sanitized HTML on `$...$` segments, rendering each formula
 * with KaTeX and leaving everything else as the original sanitized
 * markup. A malformed/unclosed `$` is left as literal text — KaTeX
 * errors are caught per-segment so one bad formula can't break the
 * whole question's rendering. */
function renderWithFormulas(html: string): string {
  return html.replace(/\$([^$]+)\$/g, (_match, formula: string) => {
    try {
      return katex.renderToString(formula, { throwOnError: false, displayMode: false });
    } catch {
      return `$${formula}$`; // malformed LaTeX — show the raw delimited text rather than crashing
    }
  });
}

export function FormulaText({ html, className }: FormulaTextProps) {
  const rendered = useMemo(() => renderWithFormulas(html), [html]);
  // eslint-disable-next-line react/no-danger -- `html` is always the
  // backend's own Sprint 32 bleach-sanitized output (see the module
  // docstring above); katex.renderToString's own output is also safe,
  // well-known-safe markup, not arbitrary user HTML.
  return <span className={className} dangerouslySetInnerHTML={{ __html: rendered }} />;
}
