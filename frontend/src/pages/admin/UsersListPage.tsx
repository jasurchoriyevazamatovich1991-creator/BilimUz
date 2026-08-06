/**
 * Sprint 15 — List/Search/Filter/Pagination only (approved decision:
 * no Create, no Delete anywhere on this page — the backend has neither
 * endpoint). Reuses shadcn/ui Input (their first real consumer, per
 * the architecture doc's Risk #4) and the existing ErrorState/
 * UnavailableState family from Sprint 14.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/layout/ErrorState";
import { StatusBadge } from "@/components/users/StatusBadge";
import { useUsersList } from "@/hooks/useUsers";
import { useRoles, useRoleNameLookup } from "@/hooks/useRoles";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

const PER_PAGE = 20;

export function UsersListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [roleId, setRoleId] = useState<string>("");
  const [status, setStatus] = useState<string>("");

  const debouncedSearch = useDebouncedValue(searchInput, 400);
  const { data: roles } = useRoles();
  const roleName = useRoleNameLookup();

  const { data, isLoading, isError } = useUsersList({
    page,
    per_page: PER_PAGE,
    search: debouncedSearch || undefined,
    role_id: roleId || undefined,
    status: status || undefined,
  });

  function handleFilterChange(setter: (v: string) => void, value: string) {
    setter(value);
    setPage(1); // any filter change resets to page 1 — stale pagination on a new filter would be confusing
  }

  if (isError) {
    return <ErrorState title="Foydalanuvchilar" />;
  }

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold text-foreground">Foydalanuvchilar</h1>

      <div className="mb-4 flex flex-wrap gap-3">
        <Input
          placeholder="Qidirish (ism, familiya)..."
          value={searchInput}
          onChange={(e) => {
            setSearchInput(e.target.value);
            setPage(1);
          }}
          className="max-w-xs"
        />
        <select
          value={roleId}
          onChange={(e) => handleFilterChange(setRoleId, e.target.value)}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm"
        >
          <option value="">Barcha rollar</option>
          {roles?.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </select>
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
              <th className="px-4 py-3 font-medium">Ism</th>
              <th className="px-4 py-3 font-medium">Aloqa</th>
              <th className="px-4 py-3 font-medium">Rol</th>
              <th className="px-4 py-3 font-medium">Holat</th>
              <th className="px-4 py-3 font-medium">Oxirgi kirish</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-foreground/50">
                  Yuklanmoqda...
                </td>
              </tr>
            ) : data && data.items.length > 0 ? (
              data.items.map((user) => (
                <tr
                  key={user.id}
                  onClick={() => navigate(`/admin/users/${user.id}`)}
                  className="cursor-pointer border-b border-border last:border-0 hover:bg-primary/5"
                >
                  <td className="px-4 py-3">{user.first_name} {user.last_name}</td>
                  <td className="px-4 py-3 text-foreground/60">{user.phone ?? user.email ?? "—"}</td>
                  <td className="px-4 py-3">{roleName(user.role_id)}</td>
                  <td className="px-4 py-3"><StatusBadge status={user.status} /></td>
                  <td className="px-4 py-3 text-foreground/60">{user.last_login ? new Date(user.last_login).toLocaleDateString() : "—"}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-foreground/50">
                  Foydalanuvchi topilmadi
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {data && data.meta.total_pages > 1 ? (
        <div className="mt-4 flex items-center justify-between text-sm text-foreground/60">
          <span>
            {data.meta.total} tadan {(page - 1) * PER_PAGE + 1}-{Math.min(page * PER_PAGE, data.meta.total)}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="rounded-md border border-border px-3 py-1.5 disabled:opacity-40"
            >
              Oldingi
            </button>
            <button
              type="button"
              disabled={page >= data.meta.total_pages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded-md border border-border px-3 py-1.5 disabled:opacity-40"
            >
              Keyingi
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
