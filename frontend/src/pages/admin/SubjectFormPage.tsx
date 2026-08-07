/**
 * Mirrors SchoolFormPage.tsx's structure (Sprint 16) — shared
 * Create/Edit, read-only rendering for non-writers. New this sprint:
 * HTML5 `<input type="color">` for `color` (approved decision — no new
 * UI library). The native color input always yields `#RRGGBB` lowercase
 * hex, matching the backend's own hex validation exactly.
 */
import { useState, useEffect, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/layout/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { useSubject, useCreateSubject, useUpdateSubject, useDeleteSubject } from "@/hooks/useSubjects";
import { useAuthStore } from "@/store/authStore";

const DEFAULT_COLOR = "#0c447c"; // matches the platform's own documented brand primary (Sprint 13's tailwind.config.js)

export function SubjectFormPage() {
  const { subjectId } = useParams<{ subjectId: string }>();
  const isEditMode = !!subjectId;
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const canWrite = currentUser?.role === "Admin" || currentUser?.role === "Super Admin";

  const { data: subject, isLoading, isError } = useSubject(subjectId);
  const createSubject = useCreateSubject();
  const updateSubject = useUpdateSubject(subjectId ?? "");
  const deleteSubject = useDeleteSubject();

  const [name, setName] = useState("");
  const [icon, setIcon] = useState("");
  const [color, setColor] = useState(DEFAULT_COLOR);
  const [status, setStatus] = useState("active");
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  useEffect(() => {
    if (subject) {
      setName(subject.name);
      setIcon(subject.icon ?? "");
      setColor(subject.color ?? DEFAULT_COLOR);
      setStatus(subject.status);
    }
  }, [subject]);

  useEffect(() => {
    if (currentUser && !canWrite && !isEditMode) {
      navigate("/admin/subjects", { replace: true });
    }
  }, [currentUser, canWrite, isEditMode, navigate]);

  if (!canWrite && !isEditMode) return null;
  if (isEditMode && isError) return <ErrorState title="Fan" />;
  if (isEditMode && (isLoading || !subject)) return <p className="text-sm text-foreground/50">Yuklanmoqda...</p>;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const payload = { name, icon: icon || undefined, color };
    if (isEditMode) {
      updateSubject.mutate({ ...payload, status }, { onSuccess: () => navigate(`/admin/subjects/${subjectId}`) });
    } else {
      createSubject.mutate(payload, { onSuccess: () => navigate("/admin/subjects") });
    }
  }

  function handleConfirmDelete() {
    if (!subjectId) return;
    deleteSubject.mutate(subjectId, { onSuccess: () => navigate("/admin/subjects") });
  }

  const isSubmitting = createSubject.isPending || updateSubject.isPending;

  return (
    <div className="max-w-2xl">
      <button type="button" onClick={() => navigate("/admin/subjects")} className="mb-4 text-sm text-primary hover:underline">
        ← Ro'yxatga qaytish
      </button>

      <Card>
        <CardHeader>
          <CardTitle>{!canWrite ? "Fan ma'lumotlari" : isEditMode ? "Fanni tahrirlash" : "Yangi fan"}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="name" className="mb-1 block text-sm font-medium text-foreground">Nomi</label>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} disabled={!canWrite} />
            </div>
            <div>
              <label htmlFor="icon" className="mb-1 block text-sm font-medium text-foreground">Ikonka (ixtiyoriy)</label>
              <Input id="icon" value={icon} onChange={(e) => setIcon(e.target.value)} disabled={!canWrite} />
            </div>
            <div>
              <label htmlFor="color" className="mb-1 block text-sm font-medium text-foreground">Rang</label>
              <div className="flex items-center gap-3">
                <input
                  id="color"
                  type="color"
                  value={color}
                  onChange={(e) => setColor(e.target.value)}
                  disabled={!canWrite}
                  className="h-10 w-14 cursor-pointer rounded-md border border-border disabled:cursor-not-allowed disabled:opacity-60"
                />
                <span className="text-sm text-foreground/60">{color}</span>
              </div>
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
        title="Fanni o'chirish"
        description={`"${name}" o'chirilsinmi? Bu amalni orqaga qaytarib bo'lmaydi.`}
        confirmLabel="O'chirish"
        isConfirming={deleteSubject.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setConfirmDeleteOpen(false)}
      />
    </div>
  );
}
