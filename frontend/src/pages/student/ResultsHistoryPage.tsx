/**
 * Sprint 34 — the "Natijalar" sidebar entry has pointed to
 * /student/results since Sprint 20, but no route/page ever existed
 * for it (confirmed in the Sprint 34 audit) — this closes that gap
 * using the real, pre-existing GET /results/me endpoint (already
 * called by resultsApi.myCount() for the dashboard card, just never
 * for a full list before now).
 *
 * Only fields ResultOut actually returns are shown: score, percentage,
 * is_passed, status, created_at. No per-question breakdown, no time
 * spent — those aren't in this schema (a real, documented backend gap,
 * not invented here).
 *
 * Test title: ResultOut has no test_title field, so each row looks its
 * test up individually via the existing useTest(testId) hook — a real
 * N+1-shaped call, but TanStack Query caches/dedupes by testId, so the
 * same test repeated across several results in one page only fetches
 * once. Accepted as the minimum-safe approach per the explicit "do not
 * invent a backend response field" instruction — a batch endpoint
 * would need a real backend change, out of this sprint's scope.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ErrorState } from "@/components/layout/ErrorState";
import { useResultsList } from "@/hooks/useResults";
import { useTest } from "@/hooks/useTests";
import type { ResultOut } from "@/api/results";

const PER_PAGE = 20;

function ResultRow({ result, onClick }: { result: ResultOut; onClick: () => void }) {
  const { data: test } = useTest(result.test_id);

  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full flex-col gap-2 rounded-lg border border-border bg-card p-4 text-left shadow-xs hover:border-primary/40 hover:shadow-sm sm:flex-row sm:items-center sm:justify-between"
    >
      <div>
        <h3 className="font-medium text-foreground">{test?.title ?? "Test"}</h3>
        <p className="mt-1 text-xs text-foreground/50">
          {new Date(result.created_at).toLocaleString("uz-UZ")}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-sm text-foreground/70">{result.score} ball ({result.percentage}%)</span>
        {result.is_passed !== null ? (
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${result.is_passed ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive"}`}>
            {result.is_passed ? "O'tdingiz" : "O'ta olmadingiz"}
          </span>
        ) : null}
      </div>
    </button>
  );
}

export function ResultsHistoryPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = useResultsList({ page, per_page: PER_PAGE });

  if (isError) return <ErrorState title="Natijalar" />;

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold text-foreground">Natijalar</h1>

      {isLoading ? (
        <p className="text-sm text-foreground/50">Yuklanmoqda...</p>
      ) : data && data.items.length > 0 ? (
        <div className="space-y-2">
          {data.items.map((result) => (
            <ResultRow key={result.id} result={result} onClick={() => navigate(`/student/results/${result.id}`)} />
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-border p-12 text-center">
          <p className="text-sm text-foreground/60">Hozircha natijalar yo'q.</p>
        </div>
      )}

      {data && data.meta.total_pages > 1 ? (
        <div className="mt-4 flex items-center justify-between text-sm text-foreground/60">
          <span>{data.meta.total} tadan {(page - 1) * PER_PAGE + 1}-{Math.min(page * PER_PAGE, data.meta.total)}</span>
          <div className="flex gap-2">
            <button type="button" disabled={page <= 1} onClick={() => setPage(1)} className="rounded-md border border-border px-3 py-1.5 disabled:opacity-40">« Birinchi</button>
            <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="rounded-md border border-border px-3 py-1.5 disabled:opacity-40">Oldingi</button>
            <button type="button" disabled={page >= data.meta.total_pages} onClick={() => setPage((p) => p + 1)} className="rounded-md border border-border px-3 py-1.5 disabled:opacity-40">Keyingi</button>
            <button type="button" disabled={page >= data.meta.total_pages} onClick={() => setPage(data.meta.total_pages)} className="rounded-md border border-border px-3 py-1.5 disabled:opacity-40">Oxirgi »</button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
