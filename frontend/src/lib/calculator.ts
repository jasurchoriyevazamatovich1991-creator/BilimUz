/**
 * Task 6 — in-exam calculator arithmetic. A small hand-written
 * tokenizer + recursive-descent parser: the expression is NEVER passed
 * to eval/Function/setTimeout(string) — only digits, one decimal point
 * per number, + − × ÷ and parentheses are understood; anything else is
 * an "invalid" result, never executed.
 *
 * Grammar:
 *   expr   := term (("+" | "-") term)*
 *   term   := factor (("*" | "/") factor)*
 *   factor := ("+" | "-") factor | number | "(" expr ")"
 */

export type CalcResult = { ok: true; value: number; display: string } | { ok: false; error: "invalid" | "divide_by_zero" | "overflow" };

type Token = { kind: "num"; value: number } | { kind: "op"; value: "+" | "-" | "*" | "/" } | { kind: "lparen" } | { kind: "rparen" };

/** Maximum accepted expression length — keeps parsing trivially cheap. */
export const MAX_EXPRESSION_LENGTH = 200;

const OP_ALIASES: Record<string, "+" | "-" | "*" | "/"> = {
  "+": "+", "-": "-", "−": "-", "*": "*", "×": "*", "x": "*", "/": "/", "÷": "/",
};

class CalcError extends Error {
  constructor(public readonly code: "invalid" | "divide_by_zero") {
    super(code);
  }
}

export function tokenize(input: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;
  while (i < input.length) {
    const ch = input[i];
    if (ch === " ") { i++; continue; }
    if ((ch >= "0" && ch <= "9") || ch === "." || ch === ",") {
      let j = i;
      let dots = 0;
      while (j < input.length && ((input[j] >= "0" && input[j] <= "9") || input[j] === "." || input[j] === ",")) {
        if (input[j] === "." || input[j] === ",") dots++;
        j++;
      }
      const raw = input.slice(i, j).replace(",", ".");
      if (dots > 1 || raw === ".") throw new CalcError("invalid");
      tokens.push({ kind: "num", value: Number(raw) });
      i = j;
      continue;
    }
    if (ch === "(") { tokens.push({ kind: "lparen" }); i++; continue; }
    if (ch === ")") { tokens.push({ kind: "rparen" }); i++; continue; }
    const op = OP_ALIASES[ch];
    if (op) { tokens.push({ kind: "op", value: op }); i++; continue; }
    throw new CalcError("invalid");
  }
  return tokens;
}

function parse(tokens: Token[]): number {
  let pos = 0;
  const peek = () => tokens[pos];

  function expr(depth: number): number {
    let left = term(depth);
    for (let t = peek(); t && t.kind === "op" && (t.value === "+" || t.value === "-"); t = peek()) {
      pos++;
      const right = term(depth);
      left = t.value === "+" ? left + right : left - right;
    }
    return left;
  }

  function term(depth: number): number {
    let left = factor(depth);
    for (let t = peek(); t && t.kind === "op" && (t.value === "*" || t.value === "/"); t = peek()) {
      pos++;
      const right = factor(depth);
      if (t.value === "/") {
        if (right === 0) throw new CalcError("divide_by_zero");
        left = left / right;
      } else {
        left = left * right;
      }
    }
    return left;
  }

  function factor(depth: number): number {
    if (depth > 50) throw new CalcError("invalid");
    const t = peek();
    if (!t) throw new CalcError("invalid");
    if (t.kind === "op" && (t.value === "+" || t.value === "-")) {
      pos++;
      const v = factor(depth + 1);
      return t.value === "-" ? -v : v;
    }
    if (t.kind === "num") { pos++; return t.value; }
    if (t.kind === "lparen") {
      pos++;
      const v = expr(depth + 1);
      const close = peek();
      if (!close || close.kind !== "rparen") throw new CalcError("invalid");
      pos++;
      return v;
    }
    throw new CalcError("invalid");
  }

  const value = expr(0);
  if (pos !== tokens.length) throw new CalcError("invalid");
  return value;
}

/** Formats with at most 12 significant digits, removing binary-float noise
 * such as 0.1 + 0.2 = 0.30000000000000004 → "0.3". */
export function formatNumber(value: number): string {
  if (Object.is(value, -0)) return "0";
  const rounded = Number(value.toPrecision(12));
  if (Math.abs(rounded) >= 1e15 || (rounded !== 0 && Math.abs(rounded) < 1e-9)) return rounded.toExponential(6).replace(/\.?0+e/, "e");
  return String(rounded);
}

export function evaluateExpression(input: string): CalcResult {
  const trimmed = input.trim();
  if (trimmed.length === 0 || trimmed.length > MAX_EXPRESSION_LENGTH) return { ok: false, error: "invalid" };
  try {
    const value = parse(tokenize(trimmed));
    if (!Number.isFinite(value)) return { ok: false, error: "overflow" };
    return { ok: true, value, display: formatNumber(value) };
  } catch (err) {
    if (err instanceof CalcError) return { ok: false, error: err.code };
    return { ok: false, error: "invalid" };
  }
}

export const CALC_ERROR_LABELS: Record<"invalid" | "divide_by_zero" | "overflow", string> = {
  invalid: "Noto'g'ri ifoda",
  divide_by_zero: "Nolga bo'lib bo'lmaydi",
  overflow: "Son juda katta",
};
