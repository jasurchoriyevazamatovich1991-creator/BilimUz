/**
 * New file — no prior useResults.ts existed (only api/results.ts's
 * myCount(), Sprint 14). Read-only hooks for the Result detail page.
 */
import { useEffect } from "react";
import { useMutation, useQuery, type UseQueryResult } from "@tanstack/react-query";
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

export function useResult(resultId: string | undefined) {
  const query = useQuery({
    queryKey: ["results", "detail", resultId],
    queryFn: () => resultsApi.get(resultId as string),
    enabled: !!resultId,
  });
  useToastOnQueryError(query);
  return query;
}

/** Used only by AttemptPage.tsx's "already finished" branch (a stale
 * link or direct navigation to a finished attempt without going
 * through the normal submit flow this session) — resolves the real,
 * persisted Result id via the same idempotent create() call, safe to
 * invoke even though a Result may already exist for this attempt. */
export function useCreateResultForFinishedAttempt(attemptId: string) {
  const addToast = useToastStore((s) => s.addToast);
  return useMutation({
    mutationFn: () => resultsApi.create(attemptId),
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Natijani ko'rsatib bo'lmadi"),
  });
}
