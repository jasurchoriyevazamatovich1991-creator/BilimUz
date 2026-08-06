import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDebouncedValue } from "./useDebouncedValue";

describe("useDebouncedValue", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("returns the initial value immediately", () => {
    const { result } = renderHook(() => useDebouncedValue("a", 400));
    expect(result.current).toBe("a");
  });

  it("does not update before the delay elapses", () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 400), {
      initialProps: { value: "a" },
    });
    rerender({ value: "b" });
    act(() => vi.advanceTimersByTime(300));
    expect(result.current).toBe("a");
  });

  it("updates after the delay elapses", () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 400), {
      initialProps: { value: "a" },
    });
    rerender({ value: "b" });
    act(() => vi.advanceTimersByTime(400));
    expect(result.current).toBe("b");
  });

  it("resets the timer on rapid successive changes (only the last value wins)", () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 400), {
      initialProps: { value: "a" },
    });
    rerender({ value: "ab" });
    act(() => vi.advanceTimersByTime(200));
    rerender({ value: "abc" });
    act(() => vi.advanceTimersByTime(200));
    expect(result.current).toBe("a"); // 400ms never elapsed uninterrupted
    act(() => vi.advanceTimersByTime(200));
    expect(result.current).toBe("abc");
  });
});
