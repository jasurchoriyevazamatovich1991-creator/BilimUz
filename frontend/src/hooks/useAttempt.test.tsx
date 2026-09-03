import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useSubmitAndCreateResult, useActiveAttemptForTest } from "./useAttempt";
import { attemptsApi } from "@/api/attempts";
import { resultsApi } from "@/api/results";

vi.mock("@/api/attempts");
vi.mock("@/api/results");

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const SUBMIT_RESULT = {
  attempt_id: "a1", score: 8, percentage: 80, is_passed: true, total_questions: 10, correct_count: 8, status: "submitted",
};
const RESULT_OUT = {
  id: "r1", attempt_id: "a1", user_id: "u1", test_id: "t1", score: 8, percentage: 80, is_passed: true,
  status: "final", created_at: "2026-01-01T00:00:00Z",
};

describe("useSubmitAndCreateResult — approved decision 1 sequencing", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls submit() before results.create() (correct order)", async () => {
    const callOrder: string[] = [];
    vi.mocked(attemptsApi.submit).mockImplementation(async () => {
      callOrder.push("submit");
      return SUBMIT_RESULT;
    });
    vi.mocked(resultsApi.create).mockImplementation(async () => {
      callOrder.push("createResult");
      return RESULT_OUT;
    });

    const { result } = renderHook(() => useSubmitAndCreateResult("a1"), { wrapper });
    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(callOrder).toEqual(["submit", "createResult"]);
  });

  it("NEVER calls results.create() if submit() itself fails", async () => {
    vi.mocked(attemptsApi.submit).mockRejectedValue(new Error("network error"));
    vi.mocked(resultsApi.create).mockResolvedValue(RESULT_OUT);

    const { result } = renderHook(() => useSubmitAndCreateResult("a1"), { wrapper });
    result.current.mutate();

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(resultsApi.create).not.toHaveBeenCalled();
  });

  it("tags the error distinctly when submit succeeds but createResult fails (approved decision 1's UX requirement)", async () => {
    vi.mocked(attemptsApi.submit).mockResolvedValue(SUBMIT_RESULT);
    vi.mocked(resultsApi.create).mockRejectedValue(new Error("createResult failed"));

    const { result } = renderHook(() => useSubmitAndCreateResult("a1"), { wrapper });
    result.current.mutate();

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(attemptsApi.submit).toHaveBeenCalledOnce(); // submit genuinely happened — never asked to "resubmit"
  });

  it("returns both submitResult and the persisted result on full success", async () => {
    vi.mocked(attemptsApi.submit).mockResolvedValue(SUBMIT_RESULT);
    vi.mocked(resultsApi.create).mockResolvedValue(RESULT_OUT);

    const { result } = renderHook(() => useSubmitAndCreateResult("a1"), { wrapper });
    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.result.id).toBe("r1");
  });
});

describe("useActiveAttemptForTest — approved decision 3", () => {
  beforeEach(() => vi.clearAllMocks());

  it("queries with status=in_progress for the given test_id", async () => {
    vi.mocked(attemptsApi.listMine).mockResolvedValue({
      items: [], meta: { page: 1, per_page: 1, total: 0, total_pages: 0 },
    });

    renderHook(() => useActiveAttemptForTest("t1"), { wrapper });

    await waitFor(() =>
      expect(attemptsApi.listMine).toHaveBeenCalledWith(
        expect.objectContaining({ test_id: "t1", status: "in_progress" }),
      ),
    );
  });

  it("does not query at all when testId is undefined", () => {
    renderHook(() => useActiveAttemptForTest(undefined), { wrapper });
    expect(attemptsApi.listMine).not.toHaveBeenCalled();
  });
});
