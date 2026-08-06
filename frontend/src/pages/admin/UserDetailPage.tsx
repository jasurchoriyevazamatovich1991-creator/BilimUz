/**
 * View + Edit only (approved decision — no delete anywhere on this
 * page). Two genuinely separate forms, matching the backend's own
 * split: profile edit (PATCH /users/{id} — name/status) vs. role
 * change (PATCH /users/{id}/role — Super-Admin-only on the backend,
 * AND gated here in the UI too, not relying on the backend's 403 alone
 * — matching the backend's documented "never bundle privilege
 * escalation with an ordinary edit" intent).
 */
import { useState, useEffect, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/layout/ErrorState";
import { StatusBadge } from "@/components/users/StatusBadge";
import { useUser, useUpdateUser, useChangeUserRole } from "@/hooks/useUsers";
import { useRoles } from "@/hooks/useRoles";
import { useAuthStore } from "@/store/authStore";

export function UserDetailPage() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const isSuperAdmin = currentUser?.role === "Super Admin";

  const { data: user, isLoading, isError } = useUser(userId);
  const { data: roles } = useRoles();
  const updateUser = useUpdateUser(userId ?? "");
  const changeRole = useChangeUserRole(userId ?? "");

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [status, setStatus] = useState<"active" | "inactive">("active");
  const [selectedRoleId, setSelectedRoleId] = useState("");

  useEffect(() => {
    if (user) {
      setFirstName(user.first_name);
      setLastName(user.last_name);
      // "banned"/"pending_verification" are not backend-settable (see
      // api/users.ts) — the edit form's own status control only ever
      // offers active/inactive, so it defaults to "active" for a user
      // in a state this form can't represent, rather than crashing.
      setStatus(user.status === "inactive" ? "inactive" : "active");
      setSelectedRoleId(user.role_id);
    }
  }, [user]);

  if (!userId) return null;
  if (isError) return <ErrorState title="Foydalanuvchi" />;
  if (isLoading || !user) return <p className="text-sm text-foreground/50">Yuklanmoqda...</p>;

  function handleProfileSubmit(e: FormEvent) {
    e.preventDefault();
    updateUser.mutate({ first_name: firstName, last_name: lastName, status });
  }

  function handleRoleSubmit(e: FormEvent) {
    e.preventDefault();
    if (selectedRoleId !== user!.role_id) {
      changeRole.mutate(selectedRoleId);
    }
  }

  return (
    <div className="max-w-2xl">
      <button type="button" onClick={() => navigate("/admin/users")} className="mb-4 text-sm text-primary hover:underline">
        ← Ro'yxatga qaytish
      </button>

      <div className="mb-6 flex items-center gap-3">
        <h1 className="text-xl font-semibold text-foreground">{user.first_name} {user.last_name}</h1>
        <StatusBadge status={user.status} />
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Profil ma'lumotlari</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleProfileSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="firstName" className="mb-1 block text-sm font-medium text-foreground">Ism</label>
                <Input id="firstName" value={firstName} onChange={(e) => setFirstName(e.target.value)} required minLength={2} />
              </div>
              <div>
                <label htmlFor="lastName" className="mb-1 block text-sm font-medium text-foreground">Familiya</label>
                <Input id="lastName" value={lastName} onChange={(e) => setLastName(e.target.value)} required minLength={2} />
              </div>
            </div>
            <div>
              <label htmlFor="status" className="mb-1 block text-sm font-medium text-foreground">Holat</label>
              <select
                id="status"
                value={status}
                onChange={(e) => setStatus(e.target.value as "active" | "inactive")}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              >
                <option value="active">active</option>
                <option value="inactive">inactive</option>
              </select>
            </div>
            <Button type="submit" disabled={updateUser.isPending}>
              {updateUser.isPending ? "Saqlanmoqda..." : "Saqlash"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {isSuperAdmin ? (
        <Card>
          <CardHeader>
            <CardTitle>Rolni o'zgartirish</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleRoleSubmit} className="flex items-end gap-3">
              <div className="flex-1">
                <select
                  value={selectedRoleId}
                  onChange={(e) => setSelectedRoleId(e.target.value)}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                >
                  {roles?.map((r) => (
                    <option key={r.id} value={r.id}>{r.name}</option>
                  ))}
                </select>
              </div>
              <Button type="submit" variant="outline" disabled={changeRole.isPending || selectedRoleId === user.role_id}>
                {changeRole.isPending ? "O'zgartirilmoqda..." : "O'zgartirish"}
              </Button>
            </form>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
