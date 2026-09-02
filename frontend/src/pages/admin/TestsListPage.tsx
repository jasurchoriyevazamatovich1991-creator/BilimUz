/**
 * Sprint 19 — mirrors TopicsListPage.tsx's structure. Subject/Grade/
 * Topic dropdowns read hooks/useSubjects.ts / useGrades.ts / useTopics.ts
 * read-only (same one-directional dependency pattern used throughout).
 * RBAC: Admin, Super Admin, Teacher (verified against backend).
 * `question_count` is already on TestOut — no extra call needed.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/layout/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { StatusBadge } from "@/components/users/StatusBadge";
import { useTestsList, useDeleteTest } from "@/hooks/useTests";
import { useSubjectsList } from "@/hooks/useSubjects";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useAuthStore } from "@/store/authStore";
import type { TestOut } from "@/api/tests";

const PER_PAGE = 20;

export function TestsListPage() {
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const canWrite = currentUser?.role === "Admin" || currentUser?.role === "Super Admin" || currentUser?.role === "Teacher";

  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [status, setStatus] = useState("");
  const [pendingDelete, setPendingDelete] = useState<TestOut | null>(null);

  const debouncedSearch = useDebouncedValue(searchInput, 400);
  const { data, isLoading, isError } = useTestsList({
    page,
    per_page: PER_PAGE,
    search: debouncedSearch || undefined,
    subject_id: subjectId || undefined,
    status: status || undefined,
  });
  const deleteTest = useDeleteTest();

  const { data: subjects } = useSubjectsList({ page: 1, per_page: 100 });
  const subjectName = (id: string | null) => (id ? subjects?.items.find((s) => s.id === id)?.name ?? id : "—");

  function handleFilterChange(setter: (v: string) => void, value: string) {
    setter(value);
    setPage(1);
  }

  function handleConfirmDelete() {
    if (!pendingDelete) return;
    deleteTest.mutate(pendingDelete.id, { onSuccess: () => setPendingDelete(null) });
  }

  if (isError) return <ErrorState title="Testlar" />;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">Testlar</h1>
        {canWrite ? <Button onClick={() => navigate("/admin/tests/new")}>Qo'shish</Button> : null}
      </div>

      <div className="mb-4 flex flex-wrap gap-3">
        <Input
          placeholder="Qidirish..."
          value={searchInput}
          onChange={(e) => {
            setSearchInput(e.target.value);
            setPage(1);
          }}
          className="max-w-xs"
        />
        <select
          value={subjectId}
          onChange={(e) => handleFilterChange(setSubjectId, e.target.value)}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm"
        >
          <option value="">Barcha fanlar</option>
          {subjects?.items.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
        <select
          value={status}
          onChange={(e) => handleFilterChange(setStatus, e.target.value)}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm"
        >
          <option value="">Barcha holatlar</option>
          <option value="draft">draft</option>
          <option value="published">published</option>
          <option value="archived">archived</option>
        </select>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-primary/5 text-left text-foreground/70">
            <tr>
              <th className="px-4 py-3 font-medium">Sarlavha</th>
              <th className="px-4 py-3 font-medium">Fan</th>
              <th className="px-4 py-3 font-medium">Savollar</th>
              <th className="px-4 py-3 font-medium">Davomiylik</th>
              <th className="px-4 py-3 font-medium">Holat</th>
              {canWrite ? <th className="px-4 py-3 font-medium">Amallar</th> : null}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-foreground/50">Yuklanmoqda...</td>
              </tr>
            ) : data && data.items.length > 0 ? (
              data.items.map((test) => (
                <tr key={test.id} className="border-b border-border last:border-0 hover:bg-primary/5">
                  <td onClick={() => navigate(`/admin/tests/${test.id}`)} className="cursor-pointer px-4 py-3">
                    {test.title}
                  </td>
                  <td className="px-4 py-3 text-foreground/60">{subjectName(test.subject_id)}</td>
                  <td className="px-4 py-3 text-foreground/60">{test.question_count}</td>
                  <td className="px-4 py-3 text-foreground/60">{test.duration} daq</td>
                  <td className="px-4 py-3"><StatusBadge status={test.status} /></td>
                  {canWrite ? (
                    <td className="px-4 py-3 space-x-3">
                      <button
                        type="button"
                        onClick={() => navigate(`/admin/tests/${test.id}/questions`)}
                        className="text-sm text-primary hover:underline"
                      >
                        Savollar
                      </button>
                      <button type="button" onClick={() => setPendingDelete(test)} className="text-sm text-red-600 hover:underline">
                        O'chirish
                      </button>
                    </td>
                  ) : null}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-foreground/50">Test topilmadi</td>
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

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Testni o'chirish"
        description={pendingDelete ? `"${pendingDelete.title}" o'chirilsinmi? Bu amalni orqaga qaytarib bo'lmaydi.` : ""}
        confirmLabel="O'chirish"
        isConfirming={deleteTest.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
