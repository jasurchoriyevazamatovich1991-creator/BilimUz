/**
 * Student-facing test catalog — GET /tests?status=published, public,
 * same endpoint Sprint 19's admin TestsListPage.tsx uses, just always
 * filtered to status=published (approved: draft/archived never shown
 * to a student — the backend itself would 422 a start_attempt against
 * a non-published test anyway, this is a UX nicety on top of a real
 * backend rule, not a security boundary this page provides).
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/layout/ErrorState";
import { useTestsList } from "@/hooks/useTests";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

const PER_PAGE = 20;

export function StudentTestsListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const debouncedSearch = useDebouncedValue(searchInput, 400);

  const { data, isLoading, isError } = useTestsList({
    page,
    per_page: PER_PAGE,
    search: debouncedSearch || undefined,
    status: "published",
  });

  if (isError) return <ErrorState title="Testlar" />;

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold text-foreground">Testlar</h1>

      <Input
        placeholder="Qidirish..."
        value={searchInput}
        onChange={(e) => {
          setSearchInput(e.target.value);
          setPage(1);
        }}
        className="mb-4 max-w-xs"
      />

      {isLoading ? (
        <p className="text-sm text-foreground/50">Yuklanmoqda...</p>
      ) : data && data.items.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((test) => (
            <button
              key={test.id}
              type="button"
              onClick={() => navigate(`/student/tests/${test.id}`)}
              className="rounded-lg border border-border p-4 text-left hover:bg-primary/5"
            >
              <h3 className="font-medium text-foreground">{test.title}</h3>
              <p className="mt-1 text-sm text-foreground/60">{test.question_count} ta savol · {test.duration} daqiqa</p>
            </button>
          ))}
        </div>
      ) : (
        <p className="text-sm text-foreground/50">Test topilmadi</p>
      )}

      {data && data.meta.total_pages > 1 ? (
        <div className="mt-4 flex items-center justify-between text-sm text-foreground/60">
          <span>{data.meta.total} tadan {(page - 1) * PER_PAGE + 1}-{Math.min(page * PER_PAGE, data.meta.total)}</span>
          <div className="flex gap-2">
            <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="rounded-md border border-border px-3 py-1.5 disabled:opacity-40">Oldingi</button>
            <button type="button" disabled={page >= data.meta.total_pages} onClick={() => setPage((p) => p + 1)} className="rounded-md border border-border px-3 py-1.5 disabled:opacity-40">Keyingi</button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
