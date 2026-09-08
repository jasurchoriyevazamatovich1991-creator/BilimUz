/**
 * READ-ONLY for Teacher — verified directly against backend
 * app/modules/subjects/router.py: write endpoints (create/update/delete)
 * require_roles("Admin", "Super Admin") only, Teacher is NOT included.
 * This page therefore shows a clean list with no create/edit/delete
 * controls at all — reuses useSubjectsList (Sprint 17) unmodified, no
 * new API/hook needed. Matches the approved Sprint 26 scope: "If
 * Teacher is read-only for Subjects: show a clean subject selection
 * list UI."
 */
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/layout/ErrorState";
import { StatusBadge } from "@/components/users/StatusBadge";
import { useSubjectsList } from "@/hooks/useSubjects";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

const PER_PAGE = 20;

export function TeacherSubjectsPage() {
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const debouncedSearch = useDebouncedValue(searchInput, 400);

  const { data, isLoading, isError } = useSubjectsList({ page, per_page: PER_PAGE, search: debouncedSearch || undefined });

  if (isError) return <ErrorState title="Fanlar" />;

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold text-foreground">Fanlar</h1>

      <Input
        placeholder="Qidirish..."
        value={searchInput}
        onChange={(e) => {
          setSearchInput(e.target.value);
          setPage(1);
        }}
        className="mb-4 max-w-xs"
      />

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-primary/5 text-left text-foreground/70">
            <tr>
              <th className="px-4 py-3 font-medium">Nomi</th>
              <th className="px-4 py-3 font-medium">Holat</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={2} className="px-4 py-8 text-center text-foreground/50">Yuklanmoqda...</td>
              </tr>
            ) : data && data.items.length > 0 ? (
              data.items.map((subject) => (
                <tr key={subject.id} className="border-b border-border last:border-0">
                  <td className="px-4 py-3 font-medium text-foreground">{subject.name}</td>
                  <td className="px-4 py-3"><StatusBadge status={subject.status} /></td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={2} className="px-4 py-8 text-center text-foreground/50">Fan topilmadi</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

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
