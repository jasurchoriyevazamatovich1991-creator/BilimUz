/**
 * Sprint 17 — mirrors SubjectsListPage.tsx's structure. RBAC:
 * Create/Edit/Delete = Admin, Super Admin only (same tier as Subjects,
 * NOT Topics' wider tier — verified against backend
 * require_roles("Admin", "Super Admin") on grades' write endpoints).
 * No color/icon columns (Grades has neither field, unlike Subjects).
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/layout/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { StatusBadge } from "@/components/users/StatusBadge";
import { useGradesList, useDeleteGrade } from "@/hooks/useGrades";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useAuthStore } from "@/store/authStore";
import type { GradeOut } from "@/api/grades";

const PER_PAGE = 20;

export function GradesListPage() {
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const canWrite = currentUser?.role === "Admin" || currentUser?.role === "Super Admin";

  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [status, setStatus] = useState("");
  const [pendingDelete, setPendingDelete] = useState<GradeOut | null>(null);

  const debouncedSearch = useDebouncedValue(searchInput, 400);
  const { data, isLoading, isError } = useGradesList({
    page,
    per_page: PER_PAGE,
    search: debouncedSearch || undefined,
    status: status || undefined,
  });
  const deleteGrade = useDeleteGrade();

  function handleFilterChange(setter: (v: string) => void, value: string) {
    setter(value);
    setPage(1);
  }

  function handleConfirmDelete() {
    if (!pendingDelete) return;
    deleteGrade.mutate(pendingDelete.id, { onSuccess: () => setPendingDelete(null) });
  }

  if (isError) return <ErrorState title="Sinflar" />;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">Sinflar</h1>
        {canWrite ? <Button onClick={() => navigate("/admin/grades/new")}>Qo'shish</Button> : null}
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
          <option value="archived">archived</option>
        </select>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-primary/5 text-left text-foreground/70">
            <tr>
              <th className="px-4 py-3 font-medium">Nomi</th>
              <th className="px-4 py-3 font-medium">Holat</th>
              {canWrite ? <th className="px-4 py-3 font-medium">Amallar</th> : null}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={3} className="px-4 py-8 text-center text-foreground/50">Yuklanmoqda...</td>
              </tr>
            ) : data && data.items.length > 0 ? (
              data.items.map((grade) => (
                <tr key={grade.id} className="border-b border-border last:border-0 hover:bg-primary/5">
                  <td onClick={() => navigate(`/admin/grades/${grade.id}`)} className="cursor-pointer px-4 py-3">
                    {grade.name}
                  </td>
                  <td className="px-4 py-3"><StatusBadge status={grade.status} /></td>
                  {canWrite ? (
                    <td className="px-4 py-3">
                      <button type="button" onClick={() => setPendingDelete(grade)} className="text-sm text-red-600 hover:underline">
                        O'chirish
                      </button>
                    </td>
                  ) : null}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={3} className="px-4 py-8 text-center text-foreground/50">Sinf topilmadi</td>
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
        title="Sinfni o'chirish"
        description={pendingDelete ? `"${pendingDelete.name}" o'chirilsinmi? Bu amalni orqaga qaytarib bo'lmaydi.` : ""}
        confirmLabel="O'chirish"
        isConfirming={deleteGrade.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
