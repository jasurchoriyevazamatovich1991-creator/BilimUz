/**
 * Sprint 27 — /admin/files. BACKEND GAP, confirmed directly against
 * uploads/router.py: there is NO admin-wide "list every user's
 * uploads" endpoint — only `GET /uploads/me` (the current user's own
 * files) exists, matching the same "no admin-wide list" pattern
 * already found in Results/Payments/Certificates across earlier
 * sprints. This page therefore shows the CURRENT admin's own uploaded
 * files (a real, working capability), not a platform-wide file
 * browser — the Subject/Grade/Topic/Type filter UI requested in the
 * brief would need a new backend endpoint this sprint does not invent.
 * Documented in docs/Sprint27_R2_Media_Storage.md as a real gap, not
 * silently worked around.
 */
import { useState } from "react";
import { ErrorState } from "@/components/layout/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { StatusBadge } from "@/components/users/StatusBadge";
import { FileUploader } from "@/components/uploads/FileUploader";
import { useMyUploads, useDeleteUpload, useSignedViewUrl } from "@/hooks/useUploads";
import type { UploadOut } from "@/api/uploads";

const PER_PAGE = 20;

function formatSize(bytes: number | null): string {
  if (bytes == null) return "—";
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function AdminFilesPage() {
  const [page, setPage] = useState(1);
  const [pendingDelete, setPendingDelete] = useState<UploadOut | null>(null);
  const { data, isLoading, isError } = useMyUploads({ page, per_page: PER_PAGE });
  const deleteUpload = useDeleteUpload();
  const signedViewUrl = useSignedViewUrl();

  function handleConfirmDelete() {
    if (!pendingDelete) return;
    deleteUpload.mutate(pendingDelete.id, { onSuccess: () => setPendingDelete(null) });
  }

  function handlePreview(uploadId: string) {
    signedViewUrl.mutate(uploadId, {
      onSuccess: (result) => window.open(result.view_url, "_blank", "noopener,noreferrer"),
    });
  }

  if (isError) return <ErrorState title="Fayllar" />;

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold text-foreground">Media / Fayllar</h1>

      <div className="mb-6 rounded-lg border border-border bg-card p-4">
        <FileUploader />
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-primary/5 text-left text-foreground/70">
            <tr>
              <th className="px-4 py-3 font-medium">Nomi</th>
              <th className="px-4 py-3 font-medium">Turi</th>
              <th className="px-4 py-3 font-medium">Hajmi</th>
              <th className="px-4 py-3 font-medium">Holat</th>
              <th className="px-4 py-3 font-medium">Amallar</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-foreground/50">Yuklanmoqda...</td>
              </tr>
            ) : data && data.items.length > 0 ? (
              data.items.map((file) => (
                <tr key={file.id} className="border-b border-border last:border-0 hover:bg-primary/5">
                  <td className="px-4 py-3 text-foreground">{file.file_name}</td>
                  <td className="px-4 py-3 text-foreground/60">{file.file_type}</td>
                  <td className="px-4 py-3 text-foreground/60">{formatSize(file.size_bytes)}</td>
                  <td className="px-4 py-3"><StatusBadge status={file.status} /></td>
                  <td className="px-4 py-3 space-x-3">
                    {file.status === "ready" ? (
                      <button
                        type="button"
                        onClick={() => handlePreview(file.id)}
                        disabled={signedViewUrl.isPending}
                        className="text-sm text-primary hover:underline"
                      >
                        Ko'rish
                      </button>
                    ) : null}
                    <button type="button" onClick={() => setPendingDelete(file)} className="text-sm text-destructive hover:underline">
                      O'chirish
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-foreground/50">Hozircha fayl yo'q</td>
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
        title="Faylni o'chirish"
        description={pendingDelete ? `"${pendingDelete.file_name}" o'chirilsinmi? Bu amalni orqaga qaytarib bo'lmaydi.` : ""}
        confirmLabel="O'chirish"
        isConfirming={deleteUpload.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
