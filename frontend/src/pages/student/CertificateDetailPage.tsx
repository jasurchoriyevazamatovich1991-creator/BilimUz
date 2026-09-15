/**
 * GET /certificates/{id} — ownership-protected on the backend (404 if
 * not yours, same pattern as Attempts/Results). Shows ONLY real
 * CertificateOut fields.
 *
 * Sprint 43: "Yuklab olish" (download) button added — calls
 * GET /certificates/{id}/download (never uses certificate.pdf_url
 * directly, which is an internal R2 object key, not a public link) and
 * opens the short-lived signed URL the backend returns.
 *
 * Shows "Tekshirish kodi" (verification_code) — returned by the
 * backend (see docs/Sprint21_Student_Certificates_UI.md's "Backend fix"
 * section: attached server-side from the separate CertificateVerification
 * record, no DB column added). Links to the public verify page with the
 * code pre-filled via ?code=, so the student can immediately see how a
 * third party would confirm the certificate is genuine.
 */
import { Link, useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/layout/ErrorState";
import { StatusBadge } from "@/components/users/StatusBadge";
import { useCertificate, useDownloadCertificate } from "@/hooks/useCertificates";

export function CertificateDetailPage() {
  const { certificateId } = useParams<{ certificateId: string }>();
  const navigate = useNavigate();

  const { data: certificate, isLoading, isError } = useCertificate(certificateId);
  const downloadCertificate = useDownloadCertificate();
  // The certificate itself has no test_id directly usable without a
  // result lookup — CertificateOut.result_id points at the Result, not
  // the Test. Showing the test title would require a Result fetch this
  // sprint's scope doesn't otherwise need; the certificate number and
  // its own fields are the real, always-available identity here.

  function handleDownload() {
    if (!certificateId) return;
    downloadCertificate.mutate(certificateId, {
      onSuccess: (data) => window.open(data.download_url, "_blank", "noopener,noreferrer"),
    });
  }

  if (!certificateId) return null;
  if (isError) return <ErrorState title="Sertifikat" />;
  if (isLoading || !certificate) return <p className="p-6 text-sm text-foreground/50">Yuklanmoqda...</p>;

  return (
    <div className="mx-auto max-w-xl">
      <button type="button" onClick={() => navigate("/student/certificates")} className="mb-4 text-sm text-primary hover:underline">
        ← Sertifikatlarga qaytish
      </button>

      <Card>
        <CardHeader>
          <CardTitle>Sertifikat</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="space-y-4 text-sm">
            <div>
              <dt className="text-foreground/50">Sertifikat raqami</dt>
              <dd className="font-mono text-lg font-medium text-foreground">{certificate.certificate_number}</dd>
            </div>
            <div>
              <dt className="text-foreground/50">Berilgan sana</dt>
              <dd className="text-foreground">{new Date(certificate.created_at).toLocaleDateString()}</dd>
            </div>
            <div>
              <dt className="mb-1 text-foreground/50">Holat</dt>
              <dd><StatusBadge status={certificate.status} /></dd>
            </div>
            <div>
              <dt className="text-foreground/50">Tekshirish kodi</dt>
              <dd className="font-mono text-foreground">{certificate.verification_code}</dd>
            </div>
          </dl>

          <div className="mt-6 flex flex-wrap gap-3">
            <Button onClick={handleDownload} disabled={downloadCertificate.isPending}>
              {downloadCertificate.isPending ? "Tayyorlanmoqda..." : "Yuklab olish (PDF)"}
            </Button>
            <Link to={`/certificates/verify?code=${encodeURIComponent(certificate.verification_code)}`}>
              <Button variant="outline">Kodni tekshirish</Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
