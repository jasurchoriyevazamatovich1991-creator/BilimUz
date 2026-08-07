/**
 * Sprint 16 — full CRUD (unlike Sprint 15's Users, Schools has real
 * Create/Update/Delete backend support, verified before writing this
 * page). Create/Edit/Delete controls are hidden entirely for Moderator
 * (approved decision — never shown disabled), matching the backend's
 * require_roles("Admin", "Super Admin") on write endpoints.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/layout/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { StatusBadge } from "@/components/users/StatusBadge";
import { useSchoolsList, useDeleteSchool } from "@/hooks/useSchools";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useAuthStore } from "@/store/authStore";
import { deriveDistinctValues } from "@/utils/deriveOptions";
import type { SchoolOut } from "@/api/schools";

const PER_PAGE = 20;

export function SchoolsListPage() {
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const canWrite = currentUser?.role === "Admin" || currentUser?.role === "Super Admin";

  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [region, setRegion] = useState("");
  const [status, setStatus] = useState("");
  const [pendingDelete, setPendingDelete] = useState<SchoolOut | null>(null);

  const debouncedSearch = useDebouncedValue(searchInput, 400);
  const { data, isLoading, isError } = useSchoolsList({
    page,
    per_page: PER_PAGE,
    search: debouncedSearch || undefined,
    region: region || undefined,
    status: status || undefined,
  });
  const deleteSchool = useDeleteSchool();

  const regionOptions = deriveDistinctValues(data?.items ?? [], "region");

  function handleFilterChange(setter: (v: string) => void, value: string) {
    setter(value);
    setPage(1);
  }

  function handleConfirmDelete() {
    if (!pendingDelete) return;
    deleteSchool.mutate(pendingDelete.id, { onSuccess: () => setPendingDelete(null) });
  }

  if (isError) return <ErrorState title="Maktablar" />;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">Maktablar</h1>
        {canWrite ? <Button onClick={() => navigate("/admin/schools/new")}>Qo'shish</Button> : null}
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
          value={region}
          onChange={(e) => handleFilterChange(setRegion, e.target.value)}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm"
        >
          <option value="">Barcha regionlar</option>
          {regionOptions.map((r) => (
            <option key={r} value={r}>{r}</option>
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
          <option value="archived">archived</option>
        </select>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-primary/5 text-left text-foreground/70">
            <tr>
              <th className="px-4 py-3 font-medium">Nomi</th>
              <th className="px-4 py-3 font-medium">Region / Tuman</th>
              <th className="px-4 py-3 font-medium">Telefon</th>
              <th className="px-4 py-3 font-medium">Holat</th>
              {canWrite ? <th className="px-4 py-3 font-medium">Amallar</th> : null}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-foreground/50">Yuklanmoqda...</td>
              </tr>
            ) : data && data.items.length > 0 ? (
              data.items.map((school) => (
                <tr key={school.id} className="border-b border-border last:border-0 hover:bg-primary/5">
                  <td
                    onClick={() => navigate(`/admin/schools/${school.id}`)}
                    className="cursor-pointer px-4 py-3"
                  >
                    {school.name}
                  </td>
                  <td className="px-4 py-3 text-foreground/60">{[school.region, school.district].filter(Boolean).join(" / ") || "—"}</td>
                  <td className="px-4 py-3 text-foreground/60">{school.phone ?? "—"}</td>
                  <td className="px-4 py-3"><StatusBadge status={school.status} /></td>
                  {canWrite ? (
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => setPendingDelete(school)}
                        className="text-sm text-red-600 hover:underline"
                      >
                        O'chirish
                      </button>
                    </td>
                  ) : null}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-foreground/50">Maktab topilmadi</td>
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

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Maktabni o'chirish"
        description={pendingDelete ? `"${pendingDelete.name}" o'chirilsinmi? Bu amalni orqaga qaytarib bo'lmaydi.` : ""}
        confirmLabel="O'chirish"
        isConfirming={deleteSchool.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
