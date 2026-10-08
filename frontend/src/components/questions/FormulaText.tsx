/**
 * Sprint 33 — renders `$...$`-delimited LaTeX segments within
 * question/option text via KaTeX; everything outside `$...$` is
 * treated as the ALREADY backend-sanitized HTML from Sprint 32's
 * bleach pipeline. `dangerouslySetInnerHTML` is used only for that
 * backend-sanitized segment (never for anything user-typed at this
 * component's own boundary) — matches the explicit "existing
 * sanitization contract, don't render raw unsafe HTML" requirement.
 *
 * Sprint 80 — block/display-mode LaTeX support added via `$$...$$`.
 * Audit (Sprint 80, section 4 of the task spec) confirmed NO block/
 * display LaTeX delimiter convention exists anywhere in source before
 * this sprint — only the inline `$...$` convention above, established
 * by this same file and by RichTextEditor.insertFormula(). Rather than
 * inventing an undiscovered "existing" format, `$$...$$` is added here
 * as a deliberate, minimal, explicitly-new extension: it is the
 * standard LaTeX block-math convention, the most natural sibling of
 * this project's own existing single-`$` inline convention (same
 * delimiter character, doubled, exactly like LaTeX/Markdown-math
 * conventions already do), and it is required by the Sprint 80 spec's
 * explicit "LaTeX matematik formulalar: inline va display/block holatda
 * to'g'ri ko'rinishi kerak" rendering requirement. No backend contract
 * change is needed — `$$...$$` is still plain text inside the same
 * already-sanitized question_text/option_text/explanation/stimulus_text
 * string bleach always allowed through untouched (bleach has no
 * opinion on `$`), so this is a frontend-only, purely-additive
 * rendering capability. */
import { useMemo } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";

interface FormulaTextProps {
  /** Backend-sanitized HTML (question_text/option_text/explanation/
   * stimulus_text as returned by the API) — may contain `$...$`
   * (inline) or `$$...$$` (block/display) LaTeX segments as plain text
   * within it. */
  html: string;
  className?: string;
}

/** Matches a `$$...$$` block segment (non-greedy, allows internal
 * newlines) OR a `$...$` inline segment (non-greedy, no `$` inside) —
 * tried in that order via alternation so a `$$...$$` block is never
 * mis-split into two bogus inline segments by a narrower `$...$` match
 * running first. Splits sanitized HTML on these segments, rendering
 * each formula with KaTeX (displayMode true for block, false for
 * inline) and leaving everything else as the original sanitized
 * markup. A malformed/unclosed `$`/`$$` is left as literal text —
 * KaTeX errors are caught per-segment so one bad formula can't break
 * the whole question's rendering. */
const FORMULA_PATTERN = /\$\$([\s\S]+?)\$\$|\$([^$]+?)\$/g;

function renderWithFormulas(html: string): string {
  return html.replace(FORMULA_PATTERN, (match, blockFormula: string | undefined, inlineFormula: string | undefined) => {
    const isBlock = blockFormula !== undefined;
    const formula = isBlock ? blockFormula : (inlineFormula as string);
    try {
      return katex.renderToString(formula, { throwOnError: false, displayMode: isBlock });
    } catch {
      return match; // malformed LaTeX — show the raw delimited text rather than crashing
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
