/**
 * Global toast store — client state, same Zustand pattern as authStore.
 * NOT persisted (toasts are ephemeral, session-only) — deliberately no
 * `persist` middleware here, unlike authStore.
 *
 * Used for API errors OUTSIDE forms (per approved Sprint 14 decision:
 * form errors stay as banners, per Sprint 13's documented UX — toasts
 * are the separate, NEW surface for errors that have no form to attach
 * to, e.g. a failed dashboard widget fetch).
 */
import { create } from "zustand";

export interface Toast {
  id: string;
  message: string;
  variant: "error" | "success" | "info";
}

interface ToastState {
  toasts: Toast[];
  addToast: (message: string, variant?: Toast["variant"]) => void;
  removeToast: (id: string) => void;
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  addToast: (message, variant = "error") => {
    const id = crypto.randomUUID();
    set((state) => ({ toasts: [...state.toasts, { id, message, variant }] }));
    // Auto-dismiss after 5s — no manual close needed for the common case.
    setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
    }, 5000);
  },
  removeToast: (id) => set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}));
