import { useToastStore } from "@/store/toastStore";

const VARIANT_STYLES = {
  error: "border-destructive/30 bg-destructive/10 text-destructive",
  success: "border-success/30 bg-success/10 text-success",
  info: "border-info/30 bg-info/10 text-info",
};

/** Mounted once in App.tsx, fixed-position — renders whatever's
 * currently in the toast store. Auto-dismiss is handled by the store
 * itself (setTimeout on add), this component only renders + allows
 * manual dismiss. */
export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);
  const removeToast = useToastStore((s) => s.removeToast);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          role="alert"
          className={`flex items-center justify-between gap-3 rounded-md border px-4 py-3 text-sm shadow-md ${VARIANT_STYLES[toast.variant]}`}
        >
          <span>{toast.message}</span>
          <button type="button" onClick={() => removeToast(toast.id)} className="text-current/60 hover:text-current" aria-label="Yopish">
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
