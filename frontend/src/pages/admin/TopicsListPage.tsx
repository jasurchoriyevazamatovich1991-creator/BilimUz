/**
 * Sprint 17 — the first cross-module admin CRUD page: Subject and
 * Grade dropdowns are populated by reading api/subjects.ts/api/grades.ts
 * read-only (same one-directional dependency shape the backend itself
 * uses for `topics -> subjects/grades`), never writing to those
 * modules from here.
 *
 * RBAC: Create/Edit/Delete = Admin, Super Admin, AND Teacher (verified
 * against backend require_roles("Admin", "Super Admin", "Teacher") on
 * topics' write endpoints) — a WIDER tier than Subjects/Grades, not
 * copy-pasted from either.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/layout/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { StatusBadge } from "@/components/users/StatusBadge";
import { useTopicsList, useDeleteTopic } from "@/hooks/useTopics";
import { useSubjectsList } from "@/hooks/useSubjects";
import { useGradesList } from "@/hooks/useGrades";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useAuthStore } from "@/store/authStore";
import type { TopicOut } from "@/api/topics";

const PER_PAGE = 20;

export function TopicsListPage() {
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const canWrite = currentUser?.role === "Admin" || currentUser?.role === "Super Admin" || currentUser?.role === "Teacher";

  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [gradeId, setGradeId] = useState("");
  const [status, setStatus] = useState("");
  const [pendingDelete, setPendingDelete] = useState<TopicOut | null>(null);

  const debouncedSearch = useDebouncedValue(searchInput, 400);
  const { data, isLoading, isError } = useTopicsList({
    page,
    per_page: PER_PAGE,
    search: debouncedSearch || undefined,
    subject_id: subjectId || undefined,
    grade_id: gradeId || undefined,
    status: status || undefined,
  });
  const deleteTopic = useDeleteTopic();

  // Read-only lookups for the filter dropdowns and the Subject/Grade
  // name columns — never written to from this page.
  const { data: subjects } = useSubjectsList({ page: 1, per_page: 100 });
  const { data: grades } = useGradesList({ page: 1, per_page: 100 });
  const subjectName = (id: string) => subjects?.items.find((s) => s.id === id)?.name ?? id;
  const gradeName = (id: string | null) => (id ? grades?.items.find((g) => g.id === id)?.name ?? id : "—");

  function handleFilterChange(setter: (v: string) => void, value: string) {
    setter(value);
    setPage(1);
  }

  function handleConfirmDelete() {
    if (!pendingDelete) return;
    deleteTopic.mutate(pendingDelete.id, { onSuccess: () => setPendingDelete(null) });
  }

  if (isError) return <ErrorState title="Mavzular" />;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">Mavzular</h1>
        {canWrite ? <Button onClick={() => navigate("/admin/topics/new")}>Qo'shish</Button> : null}
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
          value={gradeId}
          onChange={(e) => handleFilterChange(setGradeId, e.target.value)}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm"
        >
          <option value="">Barcha sinflar</option>
          {grades?.items.map((g) => (
            <option key={g.id} value={g.id}>{g.name}</option>
          ))}
        </select>
        <select
          value={status}
          onChange={(e) => handleFilterChange(setStatus, e.target.value)}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm"
        >
          <option value="">Barcha holatlar</option>
          <option value="active">active</option>
          <option value="inactive">inactive</option>
          <option value="archived">archived</option>
        </select>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-primary/5 text-left text-foreground/70">
            <tr>
              <th className="px-4 py-3 font-medium">Sarlavha</th>
              <th className="px-4 py-3 font-medium">Fan</th>
              <th className="px-4 py-3 font-medium">Sinf</th>
              <th className="px-4 py-3 font-medium">Holat</th>
              {canWrite ? <th className="px-4 py-3 font-medium">Amallar</th> : null}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-foreground/50">Yuklanmoqda...</td>
              </tr>
            ) : data && data.items.length > 0 ? (
              data.items.map((topic) => (
                <tr key={topic.id} className="border-b border-border last:border-0 hover:bg-primary/5">
                  <td onClick={() => navigate(`/admin/topics/${topic.id}`)} className="cursor-pointer px-4 py-3">
                    {topic.title}
                  </td>
                  <td className="px-4 py-3 text-foreground/60">{subjectName(topic.subject_id)}</td>
                  <td className="px-4 py-3 text-foreground/60">{gradeName(topic.grade_id)}</td>
                  <td className="px-4 py-3"><StatusBadge status={topic.status} /></td>
                  {canWrite ? (
                    <td className="px-4 py-3">
                      <button type="button" onClick={() => setPendingDelete(topic)} className="text-sm text-red-600 hover:underline">
                        O'chirish
                      </button>
                    </td>
                  ) : null}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-foreground/50">Mavzu topilmadi</td>
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
        title="Mavzuni o'chirish"
        description={pendingDelete ? `"${pendingDelete.title}" o'chirilsinmi? Bu amalni orqaga qaytarib bo'lmaydi.` : ""}
        confirmLabel="O'chirish"
        isConfirming={deleteTopic.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
