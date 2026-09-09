/**
 * Sprint 27 — first real page behind the "Mening fanlarim" sidebar
 * entry (was PlaceholderPage since Sprint 13). GET /subjects is public
 * (verified directly against subjects/router.py) — reuses
 * hooks/useSubjects.ts's useSubjectsList (Sprint 16) completely
 * unmodified, no new API file needed.
 *
 * SubjectOut has no `description` field (verified — only
 * id/name/icon/color/status) — not fabricated here.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/layout/ErrorState";
import { useSubjectsList } from "@/hooks/useSubjects";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

const PER_PAGE = 24;

export function StudentSubjectsPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const debouncedSearch = useDebouncedValue(searchInput, 400);

  const { data, isLoading, isError } = useSubjectsList({
    page,
    per_page: PER_PAGE,
    search: debouncedSearch || undefined,
    status: "active",
  });

  if (isError) return <ErrorState title="Fanlar" />;

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold text-foreground">Mening fanlarim</h1>

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
          {data.items.map((subject) => (
            <button
              key={subject.id}
              type="button"
              onClick={() => navigate(`/student/subjects/${subject.id}/grades`)}
              className="rounded-lg border border-border bg-card p-5 text-left shadow-xs hover:border-primary/40 hover:shadow-sm"
            >
              <div
                className="mb-3 flex h-10 w-10 items-center justify-center rounded-md text-lg"
                style={{ backgroundColor: subject.color ? `${subject.color}20` : undefined, color: subject.color ?? undefined }}
              >
                {subject.icon ?? "📘"}
              </div>
              <h3 className="font-medium text-foreground">{subject.name}</h3>
            </button>
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-border p-12 text-center">
          <p className="text-sm text-foreground/60">Hozircha fanlar mavjud emas.</p>
        </div>
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
