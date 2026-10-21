/**
 * Task 6 — on-screen calculator panel for exam sections where the admin
 * enabled it (ExamSection.calculator_enabled). Purely local state: it
 * never reads or writes answers, never touches the timer, and is not
 * persisted anywhere. Keyboard input is handled only while focus is
 * inside the panel, so typing into an answer field is never intercepted.
 * Arithmetic goes through lib/calculator.ts (no eval).
 */
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { CALC_ERROR_LABELS, MAX_EXPRESSION_LENGTH, evaluateExpression } from "@/lib/calculator";

const KEYS: { label: string; insert?: string; action?: "clear" | "back" | "equals"; aria?: string }[] = [
  { label: "C", action: "clear", aria: "Tozalash" }, { label: "(", insert: "(" }, { label: ")", insert: ")" }, { label: "⌫", action: "back", aria: "O'chirish" },
  { label: "7", insert: "7" }, { label: "8", insert: "8" }, { label: "9", insert: "9" }, { label: "÷", insert: "÷", aria: "Bo'lish" },
  { label: "4", insert: "4" }, { label: "5", insert: "5" }, { label: "6", insert: "6" }, { label: "×", insert: "×", aria: "Ko'paytirish" },
  { label: "1", insert: "1" }, { label: "2", insert: "2" }, { label: "3", insert: "3" }, { label: "−", insert: "−", aria: "Ayirish" },
  { label: "0", insert: "0" }, { label: ".", insert: ".", aria: "O'nli nuqta" }, { label: "=", action: "equals", aria: "Hisoblash" }, { label: "+", insert: "+", aria: "Qo'shish" },
];

const KEYBOARD_INSERT: Record<string, string> = {
  "+": "+", "-": "−", "*": "×", "/": "÷", "(": "(", ")": ")", ".": ".", ",": ".",
};

export function ExamCalculator({ onClose }: { onClose: () => void }) {
  const [expression, setExpression] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    panelRef.current?.focus();
  }, []);

  function insert(text: string) {
    setError(null);
    setExpression((prev) => {
      // After "=", typing a digit starts a new expression; an operator continues from the result.
      const base = lastResult !== null && prev === lastResult && /[0-9.(]/.test(text) ? "" : prev;
      return (base + text).slice(0, MAX_EXPRESSION_LENGTH);
    });
    setLastResult(null);
  }

  function clear() {
    setExpression("");
    setError(null);
    setLastResult(null);
  }

  function backspace() {
    setError(null);
    setLastResult(null);
    setExpression((prev) => prev.slice(0, -1));
  }

  function equals() {
    if (!expression) return;
    const result = evaluateExpression(expression);
    if (result.ok) {
      setExpression(result.display);
      setLastResult(result.display);
      setError(null);
    } else {
      setError(CALC_ERROR_LABELS[result.error]);
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const key = e.key;
    let handled = true;
    if (/^[0-9]$/.test(key)) insert(key);
    else if (key in KEYBOARD_INSERT) insert(KEYBOARD_INSERT[key]);
    else if (key === "Enter" || key === "=") equals();
    else if (key === "Backspace") backspace();
    else if (key === "Delete" || key.toLowerCase() === "c") clear();
    else if (key === "Escape") onClose();
    else handled = false;
    if (handled) {
      // Keep the key inside the calculator (no form submit, no page shortcuts).
      e.preventDefault();
      e.stopPropagation();
    }
  }

  function press(k: (typeof KEYS)[number]) {
    if (k.insert) insert(k.insert);
    else if (k.action === "clear") clear();
    else if (k.action === "back") backspace();
    else equals();
  }

  return (
    <div
      ref={panelRef}
      role="dialog"
      aria-label="Kalkulyator"
      tabIndex={-1}
      onKeyDown={handleKeyDown}
      data-testid="exam-calculator"
      className="fixed inset-x-4 bottom-4 z-40 mx-auto max-w-xs rounded-lg border border-border bg-background p-3 shadow-lg outline-none sm:inset-x-auto sm:right-6 sm:bottom-6"
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">Kalkulyator</span>
        <button type="button" onClick={onClose} aria-label="Kalkulyatorni yopish" className="rounded px-2 text-foreground/60 hover:bg-foreground/5">✕</button>
      </div>
      <div className="mb-1 min-h-[2.5rem] break-all rounded-md bg-foreground/5 px-3 py-2 text-right font-mono text-lg text-foreground" aria-live="polite" data-testid="calc-display">
        {expression || "0"}
      </div>
      <p className="mb-2 min-h-[1.25rem] text-right text-xs text-destructive" role={error ? "alert" : undefined}>{error ?? ""}</p>
      <div className="grid grid-cols-4 gap-1.5">
        {KEYS.map((k) => (
          <button
            key={k.label}
            type="button"
            aria-label={k.aria ?? k.label}
            onClick={() => press(k)}
            className={`h-11 rounded-md border border-border text-base font-medium hover:bg-primary/5 ${k.action === "equals" ? "bg-primary text-primary-foreground hover:bg-primary/90" : ""}`}
          >
            {k.label}
          </button>
        ))}
      </div>
    </div>
  );
}
