/**
 * RBAC: list/get = Admin, Super Admin (matches backend
 * require_roles("Admin", "Super Admin") on GET endpoints). Write
 * (Create/Edit/Delete) = SUPER ADMIN ONLY — verified directly against
 * roles/router.py's create/update/delete, a narrower tier than every
 * prior module (which allowed at least Admin, several also Teacher).
 * Not assumed from those precedents — checked fresh for this module.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/layout/ErrorState";
import { StatusBadge } from "@/components/users/StatusBadge";
import { useRolesList } from "@/hooks/useRoles";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useAuthStore } from "@/store/authStore";
import { isSystemRole } from "@/utils/systemRoles";

const PER_PAGE = 20;

export function RolesListPage() {
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const canWrite = currentUser?.role === "Super Admin";

  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [status, setStatus] = useState("");

  const debouncedSearch = useDebouncedValue(searchInput, 400);
  const { data, isLoading, isError } = useRolesList({
    page,
    per_page: PER_PAGE,
    search: debouncedSearch || undefined,
    status: status || undefined,
  });

  function handleFilterChange(setter: (v: string) => void, value: string) {
    setter(value);
    setPage(1);
  }

  if (isError) return <ErrorState title="Rollar" />;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">Rollar</h1>
        {canWrite ? <Button onClick={() => navigate("/admin/roles/new")}>Qo'shish</Button> : null}
      </div>

      <div className="mb-4 flex flex-wrap gap-3">
        <Input
          placeholder="Qidirish..."
          value={searchInput}
          onChange={(e) => {
            setSearchInput(e.target.value);
            setPage(1);
          }}
          className="max-w-xs"
        />
        <select
          value={status}
          onChange={(e) => handleFilterChange(setStatus, e.target.value)}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm"
        >
          <option value="">Barcha holatlar</option>
          <option value="active">active</option>
          <option value="inactive">inactive</option>
        </select>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-primary/5 text-left text-foreground/70">
            <tr>
              <th className="px-4 py-3 font-medium">Nomi</th>
              <th className="px-4 py-3 font-medium">Tavsif</th>
              <th className="px-4 py-3 font-medium">Turi</th>
              <th className="px-4 py-3 font-medium">Holat</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-foreground/50">Yuklanmoqda...</td>
              </tr>
            ) : data && data.items.length > 0 ? (
              data.items.map((role) => (
                <tr
                  key={role.id}
                  onClick={() => navigate(`/admin/roles/${role.id}`)}
                  className="cursor-pointer border-b border-border last:border-0 hover:bg-primary/5"
                >
                  <td className="px-4 py-3 font-medium text-foreground">{role.name}</td>
                  <td className="px-4 py-3 text-foreground/60">{role.description ?? "—"}</td>
                  <td className="px-4 py-3 text-foreground/60">{isSystemRole(role.name) ? "Tizim roli" : "Maxsus"}</td>
                  <td className="px-4 py-3"><StatusBadge status={role.status} /></td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-foreground/50">Rol topilmadi</td>
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
    </div>
  );
}
