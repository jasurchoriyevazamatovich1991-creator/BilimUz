import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { Timer } from "./Timer";

describe("Timer", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("renders the initial remaining time", () => {
    const expiresAt = new Date(Date.now() + 90 * 1000).toISOString(); // 1:30
    render(<Timer expiresAt={expiresAt} onExpire={vi.fn()} />);
    expect(screen.getByText("1:30")).toBeInTheDocument();
  });

  it("counts down as time passes", () => {
    const expiresAt = new Date(Date.now() + 65 * 1000).toISOString();
    render(<Timer expiresAt={expiresAt} onExpire={vi.fn()} />);
    act(() => vi.advanceTimersByTime(5000));
    expect(screen.getByText("1:00")).toBeInTheDocument();
  });

  it("calls onExpire exactly once when time reaches zero (race-safety)", () => {
    const onExpire = vi.fn();
    const expiresAt = new Date(Date.now() + 2000).toISOString();
    render(<Timer expiresAt={expiresAt} onExpire={onExpire} />);
    act(() => vi.advanceTimersByTime(5000)); // well past expiry
    expect(onExpire).toHaveBeenCalledOnce();
  });

  it("never calls onExpire before the deadline", () => {
    const onExpire = vi.fn();
    const expiresAt = new Date(Date.now() + 60 * 1000).toISOString();
    render(<Timer expiresAt={expiresAt} onExpire={onExpire} />);
    act(() => vi.advanceTimersByTime(30 * 1000));
    expect(onExpire).not.toHaveBeenCalled();
  });

  it("does not read from or write to localStorage (approved decision 2)", () => {
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem");
    const getItemSpy = vi.spyOn(Storage.prototype, "getItem");
    const expiresAt = new Date(Date.now() + 60 * 1000).toISOString();
    render(<Timer expiresAt={expiresAt} onExpire={vi.fn()} />);
    act(() => vi.advanceTimersByTime(3000));
    expect(setItemSpy).not.toHaveBeenCalled();
    expect(getItemSpy).not.toHaveBeenCalled();
    setItemSpy.mockRestore();
    getItemSpy.mockRestore();
  });
});
