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
 * rendering capability.
 *
 * Sprint 83 — formula matching is now scoped to text nodes only, never
 * to tag markup/attributes. Before this sprint, FORMULA_PATTERN ran a
 * single regex pass over the ENTIRE sanitized HTML string with no
 * awareness of tag boundaries. The only attribute bleach's own
 * allowlist (backend Sprint 32, RICH_TEXT_ALLOWED_ATTRIBUTES) ever lets
 * through is `href` on `<a>` — and `$` is a perfectly ordinary,
 * unescaped URL character bleach has no reason to strip. A single
 * literal `$` inside an href (e.g. `<a href="https://x.com/$cheap">link
 * </a> cost is $5 only$`) would pair with a LATER `$` elsewhere in the
 * text, and the lazily-matched span between them — `$cheap">link</a>
 * cost is $` — swallowed the attribute's closing quote, the tag's `>`,
 * and the entire `<a>...</a>` element, handing that corrupted fragment
 * to katex.renderToString() in place of real markup. Fixed by splitting
 * the HTML on tag boundaries first (`html.split(/(<[^>]*>)/)` — a
 * capturing split always alternates [text, tag, text, tag, ...], so
 * tags land at odd indices and text at even indices) and only ever
 * running FORMULA_PATTERN against the text segments; every tag segment
 * (and therefore every attribute, including `href`) is passed through
 * completely untouched, byte-for-byte. The one accepted behavioral
 * narrowing: a formula can no longer span across a tag boundary (e.g.
 * `$a<b>+</b>b$` split across an inline tag) — this was never a tested
 * or documented convention, and refusing to bridge tag boundaries is
 * the safe, minimal choice the task's "least invasive reliable fix"
 * instruction calls for, over inventing a full HTML-aware parser. */
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

/** Splits sanitized HTML on tag boundaries (`<...>`). `String.split()`
 * with a capturing group always alternates [text, tag, text, tag, ...,
 * text] — tag segments land at odd indices, text segments at even
 * indices — so callers can tell them apart by index parity alone,
 * with no separate "is this a tag" check needed. */
const TAG_SPLIT_PATTERN = /(<[^>]*>)/;

function replaceFormula(match: string, blockFormula: string | undefined, inlineFormula: string | undefined): string {
  const isBlock = blockFormula !== undefined;
  const formula = isBlock ? blockFormula : (inlineFormula as string);
  try {
    return katex.renderToString(formula, { throwOnError: false, displayMode: isBlock });
  } catch {
    return match; // malformed LaTeX — show the raw delimited text rather than crashing
  }
}

function renderWithFormulas(html: string): string {
  // Sprint 83 — only text segments (even indices) are ever scanned for
  // `$...$`/`$$...$$`; every tag segment (odd indices), attributes
  // included, is passed through byte-for-byte untouched. See the
  // module docstring above for the HTML-corruption bug this closes.
  return html
    .split(TAG_SPLIT_PATTERN)
    .map((segment, index) => (index % 2 === 0 ? segment.replace(FORMULA_PATTERN, replaceFormula) : segment))
    .join("");
}

export function FormulaText({ html, className }: FormulaTextProps) {
  const rendered = useMemo(() => renderWithFormulas(html), [html]);
  // Sprint 87 — removed a dangling `eslint-disable-next-line
  // react/no-danger` comment here: `eslint-plugin-react` is not a
  // dependency of this project (eslint.config.js only loads
  // typescript-eslint, react-hooks, react-refresh), so that rule was
  // never registered and the comment never actually suppressed
  // anything — it only tripped ESLint v9's flat-config error for a
  // disable comment targeting an unknown rule, which is what broke
  // `npm run lint` (surfaced by adding the Sprint 87 frontend CI lint
  // step). `html` is always the backend's own Sprint 32
  // bleach-sanitized output (see the module docstring above);
  // katex.renderToString's own output is also safe, well-known-safe
  // markup, not arbitrary user HTML — dangerouslySetInnerHTML is still
  // intentional and correct here, just no longer paired with a
  // disable comment for a rule this project doesn't load.
  return <span className={className} dangerouslySetInnerHTML={{ __html: rendered }} />;
}
