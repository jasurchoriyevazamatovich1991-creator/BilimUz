/**
 * Attempt lifecycle hooks — start/resume, answer-save, submit, and the
 * "start or resume" orchestration (approved decision 3). Same
 * toast-via-useEffect pattern as every prior data hook in this project.
 *
 * Approved decision 1 (Submit -> Create Result chaining) lives in
 * useSubmitAndCreateResult() below: ONE mutation the UI calls once,
 * which internally calls submit() then results.create() only if submit
 * succeeded, and reports a distinguishable error if createResult fails
 * after a successful submit (so the UI never tells the user to
 * "resubmit" something that already finished on the backend).
 */
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { attemptsApi, type AttemptListParams } from "@/api/attempts";
import { resultsApi } from "@/api/results";
import { useToastStore } from "@/store/toastStore";
import { ApiError } from "@/api/client";

function useToastOnQueryError(query: UseQueryResult<unknown, unknown>) {
  const addToast = useToastStore((s) => s.addToast);
  useEffect(() => {
    if (query.isError) {
      addToast(query.error instanceof ApiError ? query.error.message : "Ma'lumot yuklanmadi");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.isError, query.error]);
}

/** Approved decision 3: list the user's own attempts filtered by
 * test_id and status=in_progress, checked BEFORE calling start() — the
 * real backend does not itself check for an existing active attempt. */
export function useActiveAttemptForTest(testId: string | undefined) {
  const params: AttemptListParams = { page: 1, per_page: 1, test_id: testId, status: "in_progress" };
  const query = useQuery({
    queryKey: ["attempts", "active-for-test", testId],
    queryFn: () => attemptsApi.listMine(params),
    enabled: !!testId,
  });
  useToastOnQueryError(query);
  return query;
}

export function useStartAttempt() {
  const addToast = useToastStore((s) => s.addToast);
  return useMutation({
    mutationFn: (testId: string) => attemptsApi.start(testId),
    onError: (error) => {
      // 409 (MAX_ATTEMPTS_EXCEEDED) is a real, expected outcome here —
      // approved decision 3 explicitly treats it as a fallback case,
      // not an invented recovery flow. Surfaced via the normal toast
      // like any other API error, nothing special assumed about it.
      addToast(error instanceof ApiError ? error.message : "Urinishni boshlab bo'lmadi");
    },
  });
}

export function useAttempt(attemptId: string | undefined) {
  const query = useQuery({
    queryKey: ["attempts", "detail", attemptId],
    queryFn: () => attemptsApi.get(attemptId as string),
    enabled: !!attemptId,
    // Refetch on mount/focus is fine here (default TanStack behavior) —
    // this is exactly what makes refresh-recovery work (approved
    // decision 4): the browser reloads, this query refetches, the
    // backend returns the full persisted state (questions + answered
    // map), nothing is read from localStorage.
  });
  useToastOnQueryError(query);
  return query;
}

export function useSaveAnswer(attemptId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: ({ questionId, selectedOption }: { questionId: string; selectedOption: string | null }) =>
      attemptsApi.saveAnswer(attemptId, questionId, selectedOption),
    onSuccess: (_data, { questionId, selectedOption }) => {
      // Patch the cached attempt detail directly instead of a full
      // refetch — every option click would otherwise trigger a network
      // round-trip just to re-read data we already know the new value
      // of. The backend remains authoritative; this is purely a local
      // cache update matching what we just successfully persisted.
      queryClient.setQueryData(["attempts", "detail", attemptId], (old: import("@/api/attempts").AttemptDetailOut | undefined) => {
        if (!old) return old;
        const answered = old.answered.map((a) =>
          a.question_id === questionId ? { ...a, is_answered: selectedOption !== null, selected_option: selectedOption } : a,
        );
        return { ...old, answered };
      });
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Javob saqlanmadi"),
  });
}

export type SubmitAndCreateResultError = { stage: "submit" | "createResult"; message: string };

/**
 * Approved decision 1, single composed mutation. If submit() itself
 * fails, nothing further happens (normal error, safe to retry — the
 * attempt is still active). If submit() succeeds but results.create()
 * fails, the error is tagged `stage: "createResult"` specifically so
 * the UI can say "your answers were submitted, but showing the result
 * failed" instead of implying the whole submission needs to be redone
 * (submit() itself is provably done at that point — the backend
 * already transitioned the attempt to "submitted").
 */
export function useSubmitAndCreateResult(attemptId: string) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: async () => {
      const submitResult = await attemptsApi.submit(attemptId);
      try {
        const result = await resultsApi.create(attemptId);
        return { submitResult, result };
      } catch (err) {
        const message = err instanceof ApiError ? err.message : "Natija yaratib bo'lmadi";
        throw { stage: "createResult", message } satisfies SubmitAndCreateResultError;
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["attempts", "detail", attemptId] });
      queryClient.invalidateQueries({ queryKey: ["results"] });
    },
    onError: (error: unknown) => {
      const tagged = error as Partial<SubmitAndCreateResultError>;
      if (tagged?.stage === "createResult") {
        addToast(`Urinish yuborildi, lekin natijani ko'rsatib bo'lmadi: ${tagged.message}`);
      } else {
        addToast(error instanceof ApiError ? error.message : "Yuborib bo'lmadi");
      }
    },
  });
}
