/**
 * Mirrors TopicFormPage.tsx's structure, with two things new this
 * sprint: (1) subject_id/grade_id/topic_id are ALL optional and remain
 * editable after creation (verified — unlike every prior module's
 * immutable-parent shape, nothing here is locked); (2) a Publish button
 * (approved decision 2: NO Archive button — only what the backend
 * actually supports), shown only when status is "draft" and
 * question_count > 0, matching the backend's own precondition
 * (verified in tests/router.py's publish_test docstring) so the button
 * is never shown in a state where clicking it would just 409.
 */
import { useState, useEffect, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/layout/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { useTest, useCreateTest, useUpdateTest, usePublishTest, useDeleteTest } from "@/hooks/useTests";
import { useSubjectsList } from "@/hooks/useSubjects";
import { useGradesList } from "@/hooks/useGrades";
import { useTopicsList } from "@/hooks/useTopics";
import { useAuthStore } from "@/store/authStore";

export function TestFormPage() {
  const { testId } = useParams<{ testId: string }>();
  const isEditMode = !!testId;
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const canWrite = currentUser?.role === "Admin" || currentUser?.role === "Super Admin" || currentUser?.role === "Teacher";

  const { data: test, isLoading, isError } = useTest(testId);
  const { data: subjects } = useSubjectsList({ page: 1, per_page: 100 });
  const { data: grades } = useGradesList({ page: 1, per_page: 100 });
  const { data: topics } = useTopicsList({ page: 1, per_page: 100 });
  const createTest = useCreateTest();
  const updateTest = useUpdateTest(testId ?? "");
  const publishTest = usePublishTest(testId ?? "");
  const deleteTest = useDeleteTest();

  const [subjectId, setSubjectId] = useState("");
  const [gradeId, setGradeId] = useState("");
  const [topicId, setTopicId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [difficulty, setDifficulty] = useState("medium");
  const [duration, setDuration] = useState(60);
  const [passingScore, setPassingScore] = useState("");
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  useEffect(() => {
    if (test) {
      setSubjectId(test.subject_id ?? "");
      setGradeId(test.grade_id ?? "");
      setTopicId(test.topic_id ?? "");
      setTitle(test.title);
      setDescription(test.description ?? "");
      setDifficulty(test.difficulty);
      setDuration(test.duration);
      setPassingScore(test.passing_score != null ? String(test.passing_score) : "");
    }
  }, [test]);

  useEffect(() => {
    if (currentUser && !canWrite && !isEditMode) {
      navigate("/admin/tests", { replace: true });
    }
  }, [currentUser, canWrite, isEditMode, navigate]);

  if (!canWrite && !isEditMode) return null;
  if (isEditMode && isError) return <ErrorState title="Test" />;
  if (isEditMode && (isLoading || !test)) return <p className="text-sm text-foreground/50">Yuklanmoqda...</p>;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const payload = {
      subject_id: subjectId || undefined,
      grade_id: gradeId || undefined,
      topic_id: topicId || undefined,
      title,
      description: description || undefined,
      difficulty,
      duration,
      passing_score: passingScore ? Number(passingScore) : undefined,
    };
    if (isEditMode) {
      updateTest.mutate(payload, { onSuccess: () => navigate(`/admin/tests/${testId}`) });
    } else {
      createTest.mutate(payload, { onSuccess: () => navigate("/admin/tests") });
    }
  }

  function handleConfirmDelete() {
    if (!testId) return;
    deleteTest.mutate(testId, { onSuccess: () => navigate("/admin/tests") });
  }

  const isSubmitting = createTest.isPending || updateTest.isPending;
  const canPublish = isEditMode && test?.status === "draft" && (test?.question_count ?? 0) > 0;

  return (
    <div className="max-w-2xl">
      <button type="button" onClick={() => navigate("/admin/tests")} className="mb-4 text-sm text-primary hover:underline">
        ← Ro'yxatga qaytish
      </button>

      <Card>
        <CardHeader>
          <CardTitle>{!canWrite ? "Test ma'lumotlari" : isEditMode ? "Testni tahrirlash" : "Yangi test"}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="title" className="mb-1 block text-sm font-medium text-foreground">Sarlavha</label>
              <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} required minLength={2} disabled={!canWrite} />
            </div>
            <div>
              <label htmlFor="description" className="mb-1 block text-sm font-medium text-foreground">Tavsif (ixtiyoriy)</label>
              <Input id="description" value={description} onChange={(e) => setDescription(e.target.value)} disabled={!canWrite} />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label htmlFor="subjectId" className="mb-1 block text-sm font-medium text-foreground">Fan</label>
                <select id="subjectId" value={subjectId} onChange={(e) => setSubjectId(e.target.value)} disabled={!canWrite} className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm disabled:opacity-60">
                  <option value="">Tanlanmagan</option>
                  {subjects?.items.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              <div>
                <label htmlFor="gradeId" className="mb-1 block text-sm font-medium text-foreground">Sinf</label>
                <select id="gradeId" value={gradeId} onChange={(e) => setGradeId(e.target.value)} disabled={!canWrite} className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm disabled:opacity-60">
                  <option value="">Tanlanmagan</option>
                  {grades?.items.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
                </select>
              </div>
              <div>
                <label htmlFor="topicId" className="mb-1 block text-sm font-medium text-foreground">Mavzu</label>
                <select id="topicId" value={topicId} onChange={(e) => setTopicId(e.target.value)} disabled={!canWrite} className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm disabled:opacity-60">
                  <option value="">Tanlanmagan</option>
                  {topics?.items.map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label htmlFor="difficulty" className="mb-1 block text-sm font-medium text-foreground">Qiyinlik</label>
                <select id="difficulty" value={difficulty} onChange={(e) => setDifficulty(e.target.value)} disabled={!canWrite} className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm disabled:opacity-60">
                  <option value="easy">easy</option>
                  <option value="medium">medium</option>
                  <option value="hard">hard</option>
                </select>
              </div>
              <div>
                <label htmlFor="duration" className="mb-1 block text-sm font-medium text-foreground">Davomiylik (daqiqa)</label>
                <Input id="duration" type="number" min={1} value={duration} onChange={(e) => setDuration(Number(e.target.value))} disabled={!canWrite} />
              </div>
              <div>
                <label htmlFor="passingScore" className="mb-1 block text-sm font-medium text-foreground">O'tish bali (%)</label>
                <Input id="passingScore" type="number" min={0} max={100} value={passingScore} onChange={(e) => setPassingScore(e.target.value)} disabled={!canWrite} />
              </div>
            </div>

            {canWrite ? (
              <div className="flex items-center justify-between pt-2">
                <div className="flex gap-2">
                  <Button type="submit" disabled={isSubmitting}>
                    {isSubmitting ? "Saqlanmoqda..." : "Saqlash"}
                  </Button>
                  {canPublish ? (
                    <Button type="button" variant="outline" onClick={() => publishTest.mutate()} disabled={publishTest.isPending}>
                      {publishTest.isPending ? "..." : "E'lon qilish"}
                    </Button>
                  ) : null}
                </div>
                {isEditMode ? (
                  <Button type="button" variant="destructive" onClick={() => setConfirmDeleteOpen(true)}>
                    O'chirish
                  </Button>
                ) : null}
              </div>
            ) : null}
          </form>
        </CardContent>
      </Card>

      <ConfirmDialog
        open={confirmDeleteOpen}
        title="Testni o'chirish"
        description={`"${title}" o'chirilsinmi? Bu amalni orqaga qaytarib bo'lmaydi.`}
        confirmLabel="O'chirish"
        isConfirming={deleteTest.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setConfirmDeleteOpen(false)}
      />
    </div>
  );
}
