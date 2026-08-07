/**
 * Sprint 18 — mirrors TopicsListPage.tsx's structure (Sprint 17):
 * Topic dropdown populated by reading hooks/useTopics.ts read-only
 * (same one-directional dependency shape Topics itself uses for
 * Subjects/Grades). RBAC: Create/Edit/Delete = Admin, Super Admin,
 * Teacher (verified against backend require_roles(...) — matches
 * Topics' tier exactly, NOT Subjects/Grades' narrower one).
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/layout/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { StatusBadge } from "@/components/users/StatusBadge";
import { ContentBadges } from "@/components/lessons/ContentBadges";
import { useLessonsList, useDeleteLesson } from "@/hooks/useLessons";
import { useTopicsList } from "@/hooks/useTopics";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useAuthStore } from "@/store/authStore";
import type { LessonOut } from "@/api/lessons";

const PER_PAGE = 20;

export function LessonsListPage() {
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const canWrite = currentUser?.role === "Admin" || currentUser?.role === "Super Admin" || currentUser?.role === "Teacher";

  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [topicId, setTopicId] = useState("");
  const [status, setStatus] = useState("");
  const [pendingDelete, setPendingDelete] = useState<LessonOut | null>(null);

  const debouncedSearch = useDebouncedValue(searchInput, 400);
  const { data, isLoading, isError } = useLessonsList({
    page,
    per_page: PER_PAGE,
    search: debouncedSearch || undefined,
    topic_id: topicId || undefined,
    status: status || undefined,
  });
  const deleteLesson = useDeleteLesson();

  // Read-only lookup for the Topic filter dropdown and the Topic name
  // column — never written to from this page.
  const { data: topics } = useTopicsList({ page: 1, per_page: 100 });
  const topicTitle = (id: string) => topics?.items.find((t) => t.id === id)?.title ?? id;

  function handleFilterChange(setter: (v: string) => void, value: string) {
    setter(value);
    setPage(1);
  }

  function handleConfirmDelete() {
    if (!pendingDelete) return;
    deleteLesson.mutate(pendingDelete.id, { onSuccess: () => setPendingDelete(null) });
  }

  if (isError) return <ErrorState title="Darslar" />;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">Darslar</h1>
        {canWrite ? <Button onClick={() => navigate("/admin/lessons/new")}>Qo'shish</Button> : null}
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
          value={topicId}
          onChange={(e) => handleFilterChange(setTopicId, e.target.value)}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm"
        >
          <option value="">Barcha mavzular</option>
          {topics?.items.map((t) => (
            <option key={t.id} value={t.id}>{t.title}</option>
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
              <th className="px-4 py-3 font-medium">Mavzu</th>
              <th className="px-4 py-3 font-medium">Mazmun</th>
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
              data.items.map((lesson) => (
                <tr key={lesson.id} className="border-b border-border last:border-0 hover:bg-primary/5">
                  <td onClick={() => navigate(`/admin/lessons/${lesson.id}`)} className="cursor-pointer px-4 py-3">
                    {lesson.title}
                  </td>
                  <td className="px-4 py-3 text-foreground/60">{topicTitle(lesson.topic_id)}</td>
                  <td className="px-4 py-3">
                    <ContentBadges video={lesson.video} pdf={lesson.pdf} content={lesson.content} />
                  </td>
                  <td className="px-4 py-3"><StatusBadge status={lesson.status} /></td>
                  {canWrite ? (
                    <td className="px-4 py-3">
                      <button type="button" onClick={() => setPendingDelete(lesson)} className="text-sm text-red-600 hover:underline">
                        O'chirish
                      </button>
                    </td>
                  ) : null}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-foreground/50">Dars topilmadi</td>
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
        title="Darsni o'chirish"
        description={pendingDelete ? `"${pendingDelete.title}" o'chirilsinmi? Bu amalni orqaga qaytarib bo'lmaydi.` : ""}
        confirmLabel="O'chirish"
        isConfirming={deleteLesson.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
