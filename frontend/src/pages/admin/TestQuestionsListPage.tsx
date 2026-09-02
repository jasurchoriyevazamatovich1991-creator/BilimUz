/**
 * Nested under a Test (approved decision 4: /admin/tests/:testId/questions,
 * no standalone "Questions" sidebar entry — Questions have no meaning
 * outside their parent Test). RBAC matches Tests/Topics/Lessons: Admin,
 * Super Admin, Teacher can write; everyone else (incl. Student) is
 * read-only.
 */
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/layout/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { StatusBadge } from "@/components/users/StatusBadge";
import { MediaTypeBadges } from "@/components/questions/MediaTypeBadges";
import { useQuestionsList, useDeleteQuestion } from "@/hooks/useQuestions";
import { useTest } from "@/hooks/useTests";
import { useAuthStore } from "@/store/authStore";
import type { QuestionOut } from "@/api/questions";

const PER_PAGE = 20;

export function TestQuestionsListPage() {
  const { testId } = useParams<{ testId: string }>();
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const canWrite = currentUser?.role === "Admin" || currentUser?.role === "Super Admin" || currentUser?.role === "Teacher";

  const [page, setPage] = useState(1);
  const [pendingDelete, setPendingDelete] = useState<QuestionOut | null>(null);

  const { data: test } = useTest(testId);
  const { data, isLoading, isError } = useQuestionsList({ page, per_page: PER_PAGE, test_id: testId });
  const deleteQuestion = useDeleteQuestion();

  function handleConfirmDelete() {
    if (!pendingDelete) return;
    deleteQuestion.mutate(pendingDelete.id, { onSuccess: () => setPendingDelete(null) });
  }

  if (!testId) return null;
  if (isError) return <ErrorState title="Savollar" />;

  return (
    <div>
      <button type="button" onClick={() => navigate("/admin/tests")} className="mb-4 text-sm text-primary hover:underline">
        ← Testlarga qaytish
      </button>

      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Savollar</h1>
          {test ? <p className="text-sm text-foreground/60">{test.title}</p> : null}
        </div>
        {canWrite ? <Button onClick={() => navigate(`/admin/tests/${testId}/questions/new`)}>Qo'shish</Button> : null}
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-primary/5 text-left text-foreground/70">
            <tr>
              <th className="px-4 py-3 font-medium">Matn</th>
              <th className="px-4 py-3 font-medium">Turi</th>
              <th className="px-4 py-3 font-medium">Variantlar</th>
              <th className="px-4 py-3 font-medium">Media</th>
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
              data.items.map((question) => (
                <tr key={question.id} className="border-b border-border last:border-0 hover:bg-primary/5">
                  <td
                    onClick={() => navigate(`/admin/tests/${testId}/questions/${question.id}`)}
                    className="max-w-xs cursor-pointer truncate px-4 py-3"
                  >
                    {question.question_text}
                  </td>
                  <td className="px-4 py-3 text-foreground/60">{question.question_type}</td>
                  <td className="px-4 py-3 text-foreground/60">{question.options.length}</td>
                  <td className="px-4 py-3">
                    <MediaTypeBadges mediaTypes={question.media.map((m) => m.media_type)} />
                  </td>
                  <td className="px-4 py-3"><StatusBadge status={question.status} /></td>
                  {canWrite ? (
                    <td className="px-4 py-3">
                      <button type="button" onClick={() => setPendingDelete(question)} className="text-sm text-red-600 hover:underline">
                        O'chirish
                      </button>
                    </td>
                  ) : null}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-foreground/50">Savol topilmadi</td>
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
        title="Savolni o'chirish"
        description="Bu savol o'chirilsinmi? Bu amalni orqaga qaytarib bo'lmaydi."
        confirmLabel="O'chirish"
        isConfirming={deleteQuestion.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
