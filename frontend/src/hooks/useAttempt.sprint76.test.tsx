/**
 * Sprint 76 — hook-level tests for the two new attempt hooks:
 * useModuleForAttempt (module/section name lookup) and useSubmitModule
 * (the existing Sprint 50 module-submit endpoint's frontend consumer).
 * Mirrors this file's own pre-existing useAttempt.test.tsx pattern
 * (vi.mock("@/api/attempts") + renderHook), not AttemptPage.test.tsx's
 * httpClient-spy style — these are plain hook-contract tests, no DOM.
 */
import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useModuleForAttempt, useSubmitModule } from "./useAttempt";
import { attemptsApi } from "@/api/attempts";

vi.mock("@/api/attempts");

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const MODULE_OUT = {
  id: "m2", name: "Modul 2", order_number: 1, duration: 20,
  section_id: "s1", section_name: "Bo'lim 1", section_order_number: 0,
};

describe("useModuleForAttempt — Sprint 76", () => {
  it("does not query at all when moduleId is null (non-modular attempt)", () => {
    renderHook(() => useModuleForAttempt("a1", null), { wrapper });
    expect(attemptsApi.getModule).not.toHaveBeenCalled();
  });

  it("does not query when attemptId is undefined", () => {
    renderHook(() => useModuleForAttempt(undefined, "m1"), { wrapper });
    expect(attemptsApi.getModule).not.toHaveBeenCalled();
  });

  it("fetches module metadata once both attemptId and moduleId are present", async () => {
    vi.mocked(attemptsApi.getModule).mockResolvedValue(MODULE_OUT);
    const { result } = renderHook(() => useModuleForAttempt("a1", "m2"), { wrapper });

    await waitFor(() => expect(result.current.data).toEqual(MODULE_OUT));
    expect(attemptsApi.getModule).toHaveBeenCalledWith("a1", "m2");
  });
});

describe("useSubmitModule — Sprint 76", () => {
  it("calls the existing module-submit endpoint with the given moduleId", async () => {
    vi.mocked(attemptsApi.submitModule).mockResolvedValue({ completed: false, next_module_id: "m2", result: null });
    const { result } = renderHook(() => useSubmitModule("a1"), { wrapper });

    result.current.mutate("m1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(attemptsApi.submitModule).toHaveBeenCalledWith("a1", "m1");
  });

  it("resolves with completed:false and next_module_id when routed to another module", async () => {
    vi.mocked(attemptsApi.submitModule).mockResolvedValue({ completed: false, next_module_id: "m2", result: null });
    const { result } = renderHook(() => useSubmitModule("a1"), { wrapper });

    result.current.mutate("m1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ completed: false, next_module_id: "m2", result: null });
  });

  it("resolves with completed:true and a result when the final module is submitted", async () => {
    const finalResult = { attempt_id: "a1", score: 9, percentage: 90, is_passed: true, total_questions: 10, correct_count: 9, status: "submitted" };
    vi.mocked(attemptsApi.submitModule).mockResolvedValue({ completed: true, next_module_id: null, result: finalResult });
    const { result } = renderHook(() => useSubmitModule("a1"), { wrapper });

    result.current.mutate("m2");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.completed).toBe(true);
    expect(result.current.data?.result?.score).toBe(9);
  });
});
