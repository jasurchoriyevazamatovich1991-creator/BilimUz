/**
 * Generic confirmation dialog — approved for reuse across future
 * Delete flows (Users, Subjects, Tests, etc.), not specific to Schools/
 * Learning Centers. Self-contained (backdrop + modal), built on the
 * existing shadcn/ui Button rather than a separate Dialog primitive
 * (none exists yet in components/ui/ — adding one is out of this
 * sprint's approved scope, which only asked for ConfirmDialog itself).
 *
 * Sprint 89 fix — audit finding: this dialog had no Escape-to-close and
 * moved focus nowhere on open, inconsistent with the Header dropdown's
 * own already-existing Escape-key handling (Header.tsx). A keyboard-only
 * user previously had no way to dismiss it except blindly Tab-cycling.
 * Fixed the same way Header.tsx already does it (keydown listener while
 * open), plus autofocusing the Cancel button — the safer of the two
 * actions — on mount.
 */
import { useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  isConfirming?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Tasdiqlash",
  cancelLabel = "Bekor qilish",
  isConfirming = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const cancelButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    cancelButtonRef.current?.focus();

    function handleEscape(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
    }
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-sm rounded-lg border border-border bg-background p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="confirm-dialog-title" className="text-base font-semibold text-foreground">
          {title}
        </h2>
        <p className="mt-2 text-sm text-foreground/60">{description}</p>
        <div className="mt-6 flex justify-end gap-2">
          <Button ref={cancelButtonRef} type="button" variant="outline" onClick={onCancel} disabled={isConfirming}>
            {cancelLabel}
          </Button>
          <Button type="button" variant="destructive" onClick={onConfirm} disabled={isConfirming}>
            {isConfirming ? "..." : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
