/**
 * Combined Create/Edit page, following the established Sprint 15-19
 * pattern. `name` is ALWAYS plain read-only text in edit mode — never
 * a disabled input (matches Grades' established "immutable field" UX,
 * Sprint 17) — the real backend RoleUpdateRequest has no `name` field
 * at all, for ANY role, not just system ones.
 *
 * System role protection (verified directly in roles/service.py, not
 * guessed): for a system role (see utils/systemRoles.ts), `status` can
 * ONLY be "active" (any other value 403s) and delete is always
 * blocked. This page therefore, for a system role: shows status as
 * plain read-only text (not an editable select), and shows no Delete
 * button at all.
 *
 * Permission management (this sprint's core new piece): embedded here
 * rather than a separate page, matching QuestionFormPage.tsx's
 * (Sprint 19) precedent of hosting sub-resource management inline on
 * the parent's edit page. One grant/revoke = one real API call each
 * (no bulk endpoint exists — verified) — NOT batched into a "Save"
 * step like Sprint 19's Options, since assign/revoke here are each
 * already a single, complete, independent action with their own
 * immediate feedback, not a multi-field form being composed.
 */
import { useState, useEffect, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/layout/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { useRole, useCreateRole, useUpdateRole, useDeleteRole } from "@/hooks/useRoles";
import { useRolePermissions, useAssignPermission, useRevokePermission, usePermissionsList } from "@/hooks/usePermissions";
import { useAuthStore } from "@/store/authStore";
import { isSystemRole } from "@/utils/systemRoles";

export function RoleFormPage() {
  const { roleId } = useParams<{ roleId: string }>();
  const isEditMode = !!roleId;
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const canWrite = currentUser?.role === "Super Admin";

  const { data: role, isLoading, isError } = useRole(roleId);
  const createRole = useCreateRole();
  const updateRole = useUpdateRole(roleId ?? "");
  const deleteRole = useDeleteRole();

  const [name, setName] = useState(""); // create mode only
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState("active");
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [selectedPermissionId, setSelectedPermissionId] = useState("");
  const [pendingRevoke, setPendingRevoke] = useState<{ id: string; label: string } | null>(null);

  const roleIsSystem = role ? isSystemRole(role.name) : false;

  const { data: assignedGrants } = useRolePermissions(isEditMode ? roleId : undefined);
  const { data: allPermissions } = usePermissionsList({ page: 1, per_page: 100 });
  const assignPermission = useAssignPermission(roleId ?? "");
  const revokePermission = useRevokePermission(roleId ?? "");

  useEffect(() => {
    if (role) {
      setDescription(role.description ?? "");
      setStatus(role.status);
    }
  }, [role]);

  useEffect(() => {
    if (currentUser && !canWrite && !isEditMode) {
      navigate("/admin/roles", { replace: true });
    }
  }, [currentUser, canWrite, isEditMode, navigate]);

  if (!canWrite && !isEditMode) return null;
  if (isEditMode && isError) return <ErrorState title="Rol" />;
  if (isEditMode && (isLoading || !role)) return <p className="text-sm text-foreground/50">Yuklanmoqda...</p>;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (isEditMode) {
      updateRole.mutate(
        { description: description || undefined, status: roleIsSystem ? undefined : status },
        { onSuccess: () => navigate(`/admin/roles/${roleId}`) },
      );
    } else {
      createRole.mutate({ name, description: description || undefined }, { onSuccess: () => navigate("/admin/roles") });
    }
  }

  function handleConfirmDelete() {
    if (!roleId) return;
    deleteRole.mutate(roleId, { onSuccess: () => navigate("/admin/roles") });
  }

  function handleAssign() {
    if (!selectedPermissionId) return;
    assignPermission.mutate(selectedPermissionId, { onSuccess: () => setSelectedPermissionId("") });
  }

  function handleConfirmRevoke() {
    if (!pendingRevoke) return;
    revokePermission.mutate(pendingRevoke.id, { onSuccess: () => setPendingRevoke(null) });
  }

  const isSubmitting = createRole.isPending || updateRole.isPending;
  const assignedPermissionIds = new Set((assignedGrants ?? []).map((g) => g.permission_id));
  const availableToAssign = (allPermissions?.items ?? []).filter((p) => !assignedPermissionIds.has(p.id));

  return (
    <div className="max-w-2xl">
      <button type="button" onClick={() => navigate("/admin/roles")} className="mb-4 text-sm text-primary hover:underline">
        ← Ro'yxatga qaytish
      </button>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>{!canWrite ? "Rol ma'lumotlari" : isEditMode ? "Rolni tahrirlash" : "Yangi rol"}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {isEditMode ? (
              <div>
                <span className="mb-1 block text-sm font-medium text-foreground">Nomi</span>
                <p className="rounded-md border border-dashed border-border bg-primary/5 px-3 py-2 text-sm text-foreground/70">
                  {role!.name}
                </p>
                <p className="mt-1 text-xs text-foreground/50">Nomi yaratilgandan keyin o'zgartirilmaydi.</p>
              </div>
            ) : (
              <div>
                <label htmlFor="name" className="mb-1 block text-sm font-medium text-foreground">Nomi</label>
                <Input id="name" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} />
              </div>
            )}

            <div>
              <label htmlFor="description" className="mb-1 block text-sm font-medium text-foreground">Tavsif (ixtiyoriy)</label>
              <Input id="description" value={description} onChange={(e) => setDescription(e.target.value)} disabled={!canWrite} />
            </div>

            {isEditMode ? (
              roleIsSystem ? (
                <div>
                  <span className="mb-1 block text-sm font-medium text-foreground">Holat</span>
                  <p className="rounded-md border border-dashed border-border bg-primary/5 px-3 py-2 text-sm text-foreground/70">
                    {role!.status}
                  </p>
                  <p className="mt-1 text-xs text-foreground/50">Tizim roli — holatini o'zgartirib bo'lmaydi.</p>
                </div>
              ) : (
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
              )
            ) : null}

            {canWrite ? (
              <div className="flex items-center justify-between pt-2">
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "Saqlanmoqda..." : "Saqlash"}
                </Button>
                {isEditMode && !roleIsSystem ? (
                  <Button type="button" variant="destructive" onClick={() => setConfirmDeleteOpen(true)}>
                    O'chirish
                  </Button>
                ) : null}
              </div>
            ) : null}
          </form>
        </CardContent>
      </Card>

      {isEditMode ? (
        <Card>
          <CardHeader>
            <CardTitle>Ruxsatlar</CardTitle>
          </CardHeader>
          <CardContent>
            {canWrite ? (
              <div className="mb-4 flex items-end gap-2">
                <select
                  value={selectedPermissionId}
                  onChange={(e) => setSelectedPermissionId(e.target.value)}
                  className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm"
                >
                  <option value="">Ruxsat tanlang...</option>
                  {availableToAssign.map((p) => (
                    <option key={p.id} value={p.id}>{p.module} — {p.name}</option>
                  ))}
                </select>
                <Button type="button" variant="outline" onClick={handleAssign} disabled={!selectedPermissionId || assignPermission.isPending}>
                  Biriktirish
                </Button>
              </div>
            ) : null}

            {assignedGrants && assignedGrants.length > 0 ? (
              <ul className="space-y-2">
                {assignedGrants.map((grant) => (
                  <li key={grant.id} className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm">
                    <span>
                      <span className="text-foreground/50">{grant.permission?.module ?? "—"}</span>{" "}
                      <span className="text-foreground">{grant.permission?.name ?? grant.permission_id}</span>
                    </span>
                    {canWrite ? (
                      <button
                        type="button"
                        onClick={() => setPendingRevoke({ id: grant.permission_id, label: grant.permission?.name ?? grant.permission_id })}
                        className="text-sm text-red-600 hover:underline"
                      >
                        Olib tashlash
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-foreground/50">Bu rolga hali ruxsat biriktirilmagan.</p>
            )}
          </CardContent>
        </Card>
      ) : null}

      <ConfirmDialog
        open={confirmDeleteOpen}
        title="Rolni o'chirish"
        description={role ? `"${role.name}" o'chirilsinmi? Bu amalni orqaga qaytarib bo'lmaydi.` : ""}
        confirmLabel="O'chirish"
        isConfirming={deleteRole.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setConfirmDeleteOpen(false)}
      />

      <ConfirmDialog
        open={pendingRevoke !== null}
        title="Ruxsatni olib tashlash"
        description={pendingRevoke ? `"${pendingRevoke.label}" ushbu roldan olib tashlansinmi?` : ""}
        confirmLabel="Olib tashlash"
        isConfirming={revokePermission.isPending}
        onConfirm={handleConfirmRevoke}
        onCancel={() => setPendingRevoke(null)}
      />
    </div>
  );
}
