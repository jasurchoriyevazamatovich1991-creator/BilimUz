/**
 * Mirrors the established Create/Edit shape (Sprint 15-19). `code` is
 * plain read-only text in edit mode — the real backend
 * PermissionUpdateRequest has no `code` field at all (verified —
 * immutable, since every require_permission('CODE') call across the
 * codebase depends on it staying stable, matching Roles' own `name`
 * immutability). RBAC: Super Admin only, verified against
 * permissions/router.py's write endpoints.
 */
import { useState, useEffect, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/layout/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { usePermission, useCreatePermission, useUpdatePermission, useDeletePermission } from "@/hooks/usePermissions";
import { useAuthStore } from "@/store/authStore";

export function PermissionFormPage() {
  const { permissionId } = useParams<{ permissionId: string }>();
  const isEditMode = !!permissionId;
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const canWrite = currentUser?.role === "Super Admin";

  const { data: permission, isLoading, isError } = usePermission(permissionId);
  const createPermission = useCreatePermission();
  const updatePermission = useUpdatePermission(permissionId ?? "");
  const deletePermission = useDeletePermission();

  const [name, setName] = useState("");
  const [code, setCode] = useState(""); // create mode only
  const [module, setModule] = useState(""); // create mode only
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState("active");
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  useEffect(() => {
    if (permission) {
      setName(permission.name);
      setDescription(permission.description ?? "");
      setStatus(permission.status);
    }
  }, [permission]);

  useEffect(() => {
    if (currentUser && !canWrite && !isEditMode) {
      navigate("/admin/permissions", { replace: true });
    }
  }, [currentUser, canWrite, isEditMode, navigate]);

  if (!canWrite && !isEditMode) return null;
  if (isEditMode && isError) return <ErrorState title="Ruxsat" />;
  if (isEditMode && (isLoading || !permission)) return <p className="text-sm text-foreground/50">Yuklanmoqda...</p>;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (isEditMode) {
      updatePermission.mutate(
        { name, description: description || undefined, status },
        { onSuccess: () => navigate(`/admin/permissions/${permissionId}`) },
      );
    } else {
      createPermission.mutate(
        { name, code, module, description: description || undefined },
        { onSuccess: () => navigate("/admin/permissions") },
      );
    }
  }

  function handleConfirmDelete() {
    if (!permissionId) return;
    deletePermission.mutate(permissionId, { onSuccess: () => navigate("/admin/permissions") });
  }

  const isSubmitting = createPermission.isPending || updatePermission.isPending;

  return (
    <div className="max-w-2xl">
      <button type="button" onClick={() => navigate("/admin/permissions")} className="mb-4 text-sm text-primary hover:underline">
        ← Ro'yxatga qaytish
      </button>

      <Card>
        <CardHeader>
          <CardTitle>{!canWrite ? "Ruxsat ma'lumotlari" : isEditMode ? "Ruxsatni tahrirlash" : "Yangi ruxsat"}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="name" className="mb-1 block text-sm font-medium text-foreground">Nomi</label>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} disabled={!canWrite} />
            </div>

            {isEditMode ? (
              <div>
                <span className="mb-1 block text-sm font-medium text-foreground">Kod</span>
                <p className="rounded-md border border-dashed border-border bg-primary/5 px-3 py-2 text-sm font-mono text-foreground/70">
                  {permission!.code}
                </p>
                <p className="mt-1 text-xs text-foreground/50">Kod yaratilgandan keyin o'zgartirilmaydi.</p>
              </div>
            ) : (
              <div>
                <label htmlFor="code" className="mb-1 block text-sm font-medium text-foreground">Kod</label>
                <Input id="code" value={code} onChange={(e) => setCode(e.target.value)} required placeholder="masalan: users.delete" />
              </div>
            )}

            {isEditMode ? (
              <div>
                <span className="mb-1 block text-sm font-medium text-foreground">Modul</span>
                <p className="rounded-md border border-dashed border-border bg-primary/5 px-3 py-2 text-sm text-foreground/70">
                  {permission!.module}
                </p>
              </div>
            ) : (
              <div>
                <label htmlFor="module" className="mb-1 block text-sm font-medium text-foreground">Modul</label>
                <Input id="module" value={module} onChange={(e) => setModule(e.target.value)} required placeholder="masalan: users" />
              </div>
            )}

            <div>
              <label htmlFor="description" className="mb-1 block text-sm font-medium text-foreground">Tavsif (ixtiyoriy)</label>
              <Input id="description" value={description} onChange={(e) => setDescription(e.target.value)} disabled={!canWrite} />
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
        title="Ruxsatni o'chirish"
        description={`"${name}" o'chirilsinmi? Bu amalni orqaga qaytarib bo'lmaydi.`}
        confirmLabel="O'chirish"
        isConfirming={deletePermission.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setConfirmDeleteOpen(false)}
      />
    </div>
  );
}
