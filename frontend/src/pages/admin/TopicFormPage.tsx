/**
 * Mirrors SubjectFormPage.tsx's structure. `subject_id` is required and
 * SET-ONCE (no field for it in TopicUpdateRequest — verified against
 * the backend schema, matches GradeFormPage's "name is immutable after
 * creation" pattern but for a different field). `grade_id` remains
 * editable. RBAC: Admin, Super Admin, AND Teacher (wider than
 * Subjects/Grades — see TopicsListPage.tsx's docstring).
 */
import { useState, useEffect, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/layout/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { useTopic, useCreateTopic, useUpdateTopic, useDeleteTopic } from "@/hooks/useTopics";
import { useSubjectsList } from "@/hooks/useSubjects";
import { useGradesList } from "@/hooks/useGrades";
import { useAuthStore } from "@/store/authStore";

export function TopicFormPage() {
  const { topicId } = useParams<{ topicId: string }>();
  const isEditMode = !!topicId;
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const canWrite = currentUser?.role === "Admin" || currentUser?.role === "Super Admin" || currentUser?.role === "Teacher";

  const { data: topic, isLoading, isError } = useTopic(topicId);
  const { data: subjects } = useSubjectsList({ page: 1, per_page: 100 });
  const { data: grades } = useGradesList({ page: 1, per_page: 100 });
  const createTopic = useCreateTopic();
  const updateTopic = useUpdateTopic(topicId ?? "");
  const deleteTopic = useDeleteTopic();

  const [subjectId, setSubjectId] = useState(""); // only used on CREATE — immutable after that
  const [gradeId, setGradeId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [orderNumber, setOrderNumber] = useState(1);
  const [status, setStatus] = useState("active");
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  useEffect(() => {
    if (topic) {
      setGradeId(topic.grade_id ?? "");
      setTitle(topic.title);
      setDescription(topic.description ?? "");
      setOrderNumber(topic.order_number);
      setStatus(topic.status);
    }
  }, [topic]);

  useEffect(() => {
    if (currentUser && !canWrite && !isEditMode) {
      navigate("/admin/topics", { replace: true });
    }
  }, [currentUser, canWrite, isEditMode, navigate]);

  if (!canWrite && !isEditMode) return null;
  if (isEditMode && isError) return <ErrorState title="Mavzu" />;
  if (isEditMode && (isLoading || !topic)) return <p className="text-sm text-foreground/50">Yuklanmoqda...</p>;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (isEditMode) {
      updateTopic.mutate(
        { grade_id: gradeId || undefined, title, description: description || undefined, order_number: orderNumber, status },
        { onSuccess: () => navigate(`/admin/topics/${topicId}`) },
      );
    } else {
      createTopic.mutate(
        { subject_id: subjectId, grade_id: gradeId || undefined, title, description: description || undefined, order_number: orderNumber },
        { onSuccess: () => navigate("/admin/topics") },
      );
    }
  }

  function handleConfirmDelete() {
    if (!topicId) return;
    deleteTopic.mutate(topicId, { onSuccess: () => navigate("/admin/topics") });
  }

  const isSubmitting = createTopic.isPending || updateTopic.isPending;
  const subjectDisplayName = isEditMode ? subjects?.items.find((s) => s.id === topic?.subject_id)?.name : undefined;

  return (
    <div className="max-w-2xl">
      <button type="button" onClick={() => navigate("/admin/topics")} className="mb-4 text-sm text-primary hover:underline">
        ← Ro'yxatga qaytish
      </button>

      <Card>
        <CardHeader>
          <CardTitle>{!canWrite ? "Mavzu ma'lumotlari" : isEditMode ? "Mavzuni tahrirlash" : "Yangi mavzu"}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {isEditMode ? (
              <div>
                <span className="mb-1 block text-sm font-medium text-foreground">Fan</span>
                <p className="rounded-md border border-dashed border-border bg-primary/5 px-3 py-2 text-sm text-foreground/70">
                  {subjectDisplayName ?? topic?.subject_id}
                </p>
                <p className="mt-1 text-xs text-foreground/50">Fan yaratilgandan keyin o'zgartirilmaydi.</p>
              </div>
            ) : (
              <div>
                <label htmlFor="subjectId" className="mb-1 block text-sm font-medium text-foreground">Fan</label>
                <select
                  id="subjectId"
                  value={subjectId}
                  onChange={(e) => setSubjectId(e.target.value)}
                  required
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                >
                  <option value="" disabled>Tanlang...</option>
                  {subjects?.items.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label htmlFor="gradeId" className="mb-1 block text-sm font-medium text-foreground">Sinf (ixtiyoriy)</label>
              <select
                id="gradeId"
                value={gradeId}
                onChange={(e) => setGradeId(e.target.value)}
                disabled={!canWrite}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm disabled:opacity-60"
              >
                <option value="">Tanlanmagan</option>
                {grades?.items.map((g) => (
                  <option key={g.id} value={g.id}>{g.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="title" className="mb-1 block text-sm font-medium text-foreground">Sarlavha</label>
              <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} required minLength={2} disabled={!canWrite} />
            </div>
            <div>
              <label htmlFor="description" className="mb-1 block text-sm font-medium text-foreground">Tavsif (ixtiyoriy)</label>
              <Input id="description" value={description} onChange={(e) => setDescription(e.target.value)} disabled={!canWrite} />
            </div>
            <div>
              <label htmlFor="orderNumber" className="mb-1 block text-sm font-medium text-foreground">Tartib raqami</label>
              <Input
                id="orderNumber"
                type="number"
                min={1}
                value={orderNumber}
                onChange={(e) => setOrderNumber(Number(e.target.value))}
                disabled={!canWrite}
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
        title="Mavzuni o'chirish"
        description={`"${title}" o'chirilsinmi? Bu amalni orqaga qaytarib bo'lmaydi.`}
        confirmLabel="O'chirish"
        isConfirming={deleteTopic.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setConfirmDeleteOpen(false)}
      />
    </div>
  );
}
