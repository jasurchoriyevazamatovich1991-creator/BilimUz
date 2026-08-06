import { useToastStore } from "@/store/toastStore";

const VARIANT_STYLES = {
  error: "border-red-200 bg-red-50 text-red-700",
  success: "border-green-200 bg-green-50 text-green-700",
  info: "border-blue-200 bg-blue-50 text-blue-700",
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
