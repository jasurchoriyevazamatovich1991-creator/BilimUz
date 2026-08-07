/**
 * Mirrors TopicFormPage.tsx's structure (Sprint 17). Two things new
 * this sprint:
 *   1. `type="url"` inputs for video/pdf (approved decision 2 — native
 *      browser URL validation, no new library).
 *   2. Cross-field "at least one of video/pdf/content" check (approved
 *      decision 3): submit is NEVER blocked/disabled — the check runs
 *      on submit, and if all three are empty, a single clear message
 *      renders near the fields and the mutation is never called (no
 *      malformed request reaches the backend). Matches the existing
 *      submit-time-validation convention used by every prior form
 *      (RegisterPage's password length, SubjectFormPage's name length).
 *
 * `topic_id` is set-once (approved decision 4): shown as plain
 * read-only text in edit mode, never a disabled <select> — same
 * pattern GradeFormPage.tsx already established for Grades' `name`.
 */
import { useState, useEffect, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/layout/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { useLesson, useCreateLesson, useUpdateLesson, useDeleteLesson } from "@/hooks/useLessons";
import { useTopicsList } from "@/hooks/useTopics";
import { useAuthStore } from "@/store/authStore";

export function LessonFormPage() {
  const { lessonId } = useParams<{ lessonId: string }>();
  const isEditMode = !!lessonId;
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const canWrite = currentUser?.role === "Admin" || currentUser?.role === "Super Admin" || currentUser?.role === "Teacher";

  const { data: lesson, isLoading, isError } = useLesson(lessonId);
  const { data: topics } = useTopicsList({ page: 1, per_page: 100 });
  const createLesson = useCreateLesson();
  const updateLesson = useUpdateLesson(lessonId ?? "");
  const deleteLesson = useDeleteLesson();

  const [topicId, setTopicId] = useState(""); // only used on CREATE — immutable after that
  const [title, setTitle] = useState("");
  const [video, setVideo] = useState("");
  const [pdf, setPdf] = useState("");
  const [content, setContent] = useState("");
  const [status, setStatus] = useState("active");
  const [contentError, setContentError] = useState(false);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  useEffect(() => {
    if (lesson) {
      setTitle(lesson.title);
      setVideo(lesson.video ?? "");
      setPdf(lesson.pdf ?? "");
      setContent(lesson.content ?? "");
      setStatus(lesson.status);
    }
  }, [lesson]);

  useEffect(() => {
    if (currentUser && !canWrite && !isEditMode) {
      navigate("/admin/lessons", { replace: true });
    }
  }, [currentUser, canWrite, isEditMode, navigate]);

  if (!canWrite && !isEditMode) return null;
  if (isEditMode && isError) return <ErrorState title="Dars" />;
  if (isEditMode && (isLoading || !lesson)) return <p className="text-sm text-foreground/50">Yuklanmoqda...</p>;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();

    // Cross-field rule (approved decision 3): checked on submit, never
    // via a disabled button — matches LessonCreateRequest/
    // LessonUpdateRequest's real backend model_validator exactly.
    if (!video.trim() && !pdf.trim() && !content.trim()) {
      setContentError(true);
      return;
    }
    setContentError(false);

    if (isEditMode) {
      updateLesson.mutate(
        { title, video: video || undefined, pdf: pdf || undefined, content: content || undefined, status },
        { onSuccess: () => navigate(`/admin/lessons/${lessonId}`) },
      );
    } else {
      createLesson.mutate(
        { topic_id: topicId, title, video: video || undefined, pdf: pdf || undefined, content: content || undefined },
        { onSuccess: () => navigate("/admin/lessons") },
      );
    }
  }

  function handleConfirmDelete() {
    if (!lessonId) return;
    deleteLesson.mutate(lessonId, { onSuccess: () => navigate("/admin/lessons") });
  }

  const isSubmitting = createLesson.isPending || updateLesson.isPending;
  const topicDisplayTitle = isEditMode ? topics?.items.find((t) => t.id === lesson?.topic_id)?.title : undefined;

  return (
    <div className="max-w-2xl">
      <button type="button" onClick={() => navigate("/admin/lessons")} className="mb-4 text-sm text-primary hover:underline">
        ← Ro'yxatga qaytish
      </button>

      <Card>
        <CardHeader>
          <CardTitle>{!canWrite ? "Dars ma'lumotlari" : isEditMode ? "Darsni tahrirlash" : "Yangi dars"}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {contentError ? (
              <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                Video, PDF yoki matndan kamida bittasini kiriting.
              </div>
            ) : null}

            {isEditMode ? (
              <div>
                <span className="mb-1 block text-sm font-medium text-foreground">Mavzu</span>
                <p className="rounded-md border border-dashed border-border bg-primary/5 px-3 py-2 text-sm text-foreground/70">
                  {topicDisplayTitle ?? lesson?.topic_id}
                </p>
                <p className="mt-1 text-xs text-foreground/50">Mavzu yaratilgandan keyin o'zgartirilmaydi.</p>
              </div>
            ) : (
              <div>
                <label htmlFor="topicId" className="mb-1 block text-sm font-medium text-foreground">Mavzu</label>
                <select
                  id="topicId"
                  value={topicId}
                  onChange={(e) => setTopicId(e.target.value)}
                  required
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                >
                  <option value="" disabled>Tanlang...</option>
                  {topics?.items.map((t) => (
                    <option key={t.id} value={t.id}>{t.title}</option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label htmlFor="title" className="mb-1 block text-sm font-medium text-foreground">Sarlavha</label>
              <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} required minLength={2} disabled={!canWrite} />
            </div>
            <div>
              <label htmlFor="video" className="mb-1 block text-sm font-medium text-foreground">Video URL (ixtiyoriy)</label>
              <Input
                id="video"
                type="url"
                placeholder="https://..."
                value={video}
                onChange={(e) => setVideo(e.target.value)}
                disabled={!canWrite}
              />
            </div>
            <div>
              <label htmlFor="pdf" className="mb-1 block text-sm font-medium text-foreground">PDF URL (ixtiyoriy)</label>
              <Input
                id="pdf"
                type="url"
                placeholder="https://..."
                value={pdf}
                onChange={(e) => setPdf(e.target.value)}
                disabled={!canWrite}
              />
            </div>
            <div>
              <label htmlFor="content" className="mb-1 block text-sm font-medium text-foreground">Matn (ixtiyoriy)</label>
              <textarea
                id="content"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                disabled={!canWrite}
                rows={4}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm disabled:opacity-60"
              />
            </div>
            {isEditMode ? (
              <div>
                <label htmlFor="status" className="mb-1 block text-sm font-medium text-foreground">Holat</label>
                <select
                  id="status"
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  disabled={!canWrite}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm disabled:opacity-60"
                >
                  <option value="active">active</option>
                  <option value="inactive">inactive</option>
                  <option value="archived">archived</option>
                </select>
              </div>
            ) : null}

            {canWrite ? (
              <div className="flex items-center justify-between pt-2">
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "Saqlanmoqda..." : "Saqlash"}
                </Button>
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
        title="Darsni o'chirish"
        description={`"${title}" o'chirilsinmi? Bu amalni orqaga qaytarib bo'lmaydi.`}
        confirmLabel="O'chirish"
        isConfirming={deleteLesson.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setConfirmDeleteOpen(false)}
      />
    </div>
  );
}
