import { describe, expect, it, beforeEach, vi } from "vitest";
import { useToastStore } from "./toastStore";

describe("toastStore", () => {
  beforeEach(() => {
    useToastStore.setState({ toasts: [] });
    vi.useRealTimers();
  });

  it("adds a toast with a generated id", () => {
    useToastStore.getState().addToast("Xatolik yuz berdi");
    const { toasts } = useToastStore.getState();
    expect(toasts).toHaveLength(1);
    expect(toasts[0].message).toBe("Xatolik yuz berdi");
    expect(toasts[0].variant).toBe("error"); // default variant
  });

  it("removes a toast by id", () => {
    useToastStore.getState().addToast("Test");
    const id = useToastStore.getState().toasts[0].id;
    useToastStore.getState().removeToast(id);
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });

  it("auto-dismisses after 5 seconds", () => {
    vi.useFakeTimers();
    useToastStore.getState().addToast("Vaqtinchalik xabar");
    expect(useToastStore.getState().toasts).toHaveLength(1);
    vi.advanceTimersByTime(5000);
    expect(useToastStore.getState().toasts).toHaveLength(0);
    vi.useRealTimers();
  });

  it("supports multiple simultaneous toasts", () => {
    useToastStore.getState().addToast("Birinchi");
    useToastStore.getState().addToast("Ikkinchi");
    expect(useToastStore.getState().toasts).toHaveLength(2);
  });
});
