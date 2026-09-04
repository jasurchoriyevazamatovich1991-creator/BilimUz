/**
 * GET /certificates/me — own certificates only, paginated. Same
 * list-page shape as every prior sprint (loading/error/empty/success),
 * no search/filter (the real ListParams for this endpoint only support
 * page/per_page — verified against CertificateListParams, no `search`
 * field exists, so none is built here).
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ErrorState } from "@/components/layout/ErrorState";
import { StatusBadge } from "@/components/users/StatusBadge";
import { useMyCertificates } from "@/hooks/useCertificates";

const PER_PAGE = 20;

export function CertificatesListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = useMyCertificates({ page, per_page: PER_PAGE });

  if (isError) return <ErrorState title="Sertifikatlarim" />;

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold text-foreground">Sertifikatlarim</h1>

      {isLoading ? (
        <p className="text-sm text-foreground/50">Yuklanmoqda...</p>
      ) : data && data.items.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="border-b border-border bg-primary/5 text-left text-foreground/70">
              <tr>
                <th className="px-4 py-3 font-medium">Sertifikat raqami</th>
                <th className="px-4 py-3 font-medium">Sana</th>
                <th className="px-4 py-3 font-medium">Holat</th>
                <th className="px-4 py-3 font-medium">Amallar</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((certificate) => (
                <tr key={certificate.id} className="border-b border-border last:border-0 hover:bg-primary/5">
                  <td className="px-4 py-3 font-mono text-foreground">{certificate.certificate_number}</td>
                  <td className="px-4 py-3 text-foreground/60">{new Date(certificate.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3"><StatusBadge status={certificate.status} /></td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => navigate(`/student/certificates/${certificate.id}`)}
                      className="text-sm text-primary hover:underline"
                    >
                      Ko'rish
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-border p-12 text-center">
          <p className="text-sm text-foreground/60">Sizda hali sertifikat yo'q.</p>
          <p className="mt-1 text-xs text-foreground/40">Testni muvaffaqiyatli yakunlaganingizdan so'ng sertifikat shu yerda paydo bo'ladi.</p>
        </div>
      )}

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
