/**
 * Mirrors SchoolFormPage.tsx's structure exactly (Create/Edit shared,
 * read-only rendering for non-writers viewing an existing center,
 * full redirect-away only for the Create route). See that file's
 * comments for the full rationale — not repeated here to avoid
 * duplicated prose, though the actual field logic is independent code
 * (approved decision: two separate pages, not a shared component).
 */
import { useState, useEffect, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/layout/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { useLearningCenter, useCreateLearningCenter, useUpdateLearningCenter, useDeleteLearningCenter } from "@/hooks/useLearningCenters";
import { useAuthStore } from "@/store/authStore";

export function LearningCenterFormPage() {
  const { centerId } = useParams<{ centerId: string }>();
  const isEditMode = !!centerId;
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const canWrite = currentUser?.role === "Admin" || currentUser?.role === "Super Admin";

  const { data: center, isLoading, isError } = useLearningCenter(centerId);
  const createCenter = useCreateLearningCenter();
  const updateCenter = useUpdateLearningCenter(centerId ?? "");
  const deleteCenter = useDeleteLearningCenter();

  const [name, setName] = useState("");
  const [ownerName, setOwnerName] = useState("");
  const [region, setRegion] = useState("");
  const [phone, setPhone] = useState("");
  const [status, setStatus] = useState("active");
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  useEffect(() => {
    if (center) {
      setName(center.name);
      setOwnerName(center.owner_name ?? "");
      setRegion(center.region ?? "");
      setPhone(center.phone ?? "");
      setStatus(center.status);
    }
  }, [center]);

  useEffect(() => {
    if (currentUser && !canWrite && !isEditMode) {
      navigate("/admin/learning-centers", { replace: true });
    }
  }, [currentUser, canWrite, isEditMode, navigate]);

  if (!canWrite && !isEditMode) return null;
  if (isEditMode && isError) return <ErrorState title="O'quv markazi" />;
  if (isEditMode && (isLoading || !center)) return <p className="text-sm text-foreground/50">Yuklanmoqda...</p>;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const payload = {
      name,
      owner_name: ownerName || undefined,
      region: region || undefined,
      phone: phone || undefined,
    };
    if (isEditMode) {
      updateCenter.mutate({ ...payload, status }, { onSuccess: () => navigate(`/admin/learning-centers/${centerId}`) });
    } else {
      createCenter.mutate(payload, { onSuccess: () => navigate("/admin/learning-centers") });
    }
  }

  function handleConfirmDelete() {
    if (!centerId) return;
    deleteCenter.mutate(centerId, { onSuccess: () => navigate("/admin/learning-centers") });
  }

  const isSubmitting = createCenter.isPending || updateCenter.isPending;

  return (
    <div className="max-w-2xl">
      <button type="button" onClick={() => navigate("/admin/learning-centers")} className="mb-4 text-sm text-primary hover:underline">
        ← Ro'yxatga qaytish
      </button>

      <Card>
        <CardHeader>
          <CardTitle>{!canWrite ? "O'quv markazi ma'lumotlari" : isEditMode ? "O'quv markazini tahrirlash" : "Yangi o'quv markazi"}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="name" className="mb-1 block text-sm font-medium text-foreground">Nomi</label>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} disabled={!canWrite} />
            </div>
            <div>
              <label htmlFor="ownerName" className="mb-1 block text-sm font-medium text-foreground">Egasi</label>
              <Input id="ownerName" value={ownerName} onChange={(e) => setOwnerName(e.target.value)} disabled={!canWrite} />
            </div>
            <div>
              <label htmlFor="region" className="mb-1 block text-sm font-medium text-foreground">Region</label>
              <Input id="region" value={region} onChange={(e) => setRegion(e.target.value)} disabled={!canWrite} />
            </div>
            <div>
              <label htmlFor="phone" className="mb-1 block text-sm font-medium text-foreground">Telefon</label>
              <Input id="phone" placeholder="+998712345678" value={phone} onChange={(e) => setPhone(e.target.value)} disabled={!canWrite} />
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
        title="O'quv markazini o'chirish"
        description={`"${name}" o'chirilsinmi? Bu amalni orqaga qaytarib bo'lmaydi.`}
        confirmLabel="O'chirish"
        isConfirming={deleteCenter.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setConfirmDeleteOpen(false)}
      />
    </div>
  );
}
