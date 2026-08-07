/**
 * Unlike SubjectFormPage/SchoolFormPage, this is NOT a "shared
 * Create/Edit form" in the same sense — Edit mode only ever changes
 * `status` (approved decision 4: `name` shown as PLAIN READ-ONLY TEXT,
 * never a disabled input, so the user clearly understands it cannot be
 * changed — matches GradeUpdateRequest's real shape on the backend,
 * which has no `name` field at all).
 */
import { useState, useEffect, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/layout/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { useGrade, useCreateGrade, useUpdateGrade, useDeleteGrade } from "@/hooks/useGrades";
import { useAuthStore } from "@/store/authStore";

export function GradeFormPage() {
  const { gradeId } = useParams<{ gradeId: string }>();
  const isEditMode = !!gradeId;
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const canWrite = currentUser?.role === "Admin" || currentUser?.role === "Super Admin";

  const { data: grade, isLoading, isError } = useGrade(gradeId);
  const createGrade = useCreateGrade();
  const updateGrade = useUpdateGrade(gradeId ?? "");
  const deleteGrade = useDeleteGrade();

  const [name, setName] = useState(""); // only used on the CREATE form
  const [status, setStatus] = useState("active");
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  useEffect(() => {
    if (grade) setStatus(grade.status);
  }, [grade]);

  useEffect(() => {
    if (currentUser && !canWrite && !isEditMode) {
      navigate("/admin/grades", { replace: true });
    }
  }, [currentUser, canWrite, isEditMode, navigate]);

  if (!canWrite && !isEditMode) return null;
  if (isEditMode && isError) return <ErrorState title="Sinf" />;
  if (isEditMode && (isLoading || !grade)) return <p className="text-sm text-foreground/50">Yuklanmoqda...</p>;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (isEditMode) {
      updateGrade.mutate({ status }, { onSuccess: () => navigate(`/admin/grades/${gradeId}`) });
    } else {
      createGrade.mutate({ name }, { onSuccess: () => navigate("/admin/grades") });
    }
  }

  function handleConfirmDelete() {
    if (!gradeId) return;
    deleteGrade.mutate(gradeId, { onSuccess: () => navigate("/admin/grades") });
  }

  const isSubmitting = createGrade.isPending || updateGrade.isPending;

  return (
    <div className="max-w-2xl">
      <button type="button" onClick={() => navigate("/admin/grades")} className="mb-4 text-sm text-primary hover:underline">
        ← Ro'yxatga qaytish
      </button>

      <Card>
        <CardHeader>
          <CardTitle>{!canWrite ? "Sinf ma'lumotlari" : isEditMode ? "Sinfni tahrirlash" : "Yangi sinf"}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {isEditMode ? (
              <div>
                <span className="mb-1 block text-sm font-medium text-foreground">Nomi</span>
                <p className="rounded-md border border-dashed border-border bg-primary/5 px-3 py-2 text-sm text-foreground/70">
                  {grade!.name}
                </p>
                <p className="mt-1 text-xs text-foreground/50">Nomi yaratilgandan keyin o'zgartirilmaydi.</p>
              </div>
            ) : (
              <div>
                <label htmlFor="name" className="mb-1 block text-sm font-medium text-foreground">Nomi</label>
                <Input id="name" placeholder="5-sinf" value={name} onChange={(e) => setName(e.target.value)} required minLength={1} />
              </div>
            )}

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
        title="Sinfni o'chirish"
        description={grade ? `"${grade.name}" o'chirilsinmi? Bu amalni orqaga qaytarib bo'lmaydi.` : ""}
        confirmLabel="O'chirish"
        isConfirming={deleteGrade.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setConfirmDeleteOpen(false)}
      />
    </div>
  );
}
