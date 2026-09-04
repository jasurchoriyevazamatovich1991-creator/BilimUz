/**
 * Public — GET /certificates/verify/{code}, no authentication required
 * (rendered under PublicLayout, outside ProtectedRoute entirely).
 * Shows only VerificationResultOut's real fields: certificate_number,
 * is_valid, verified_count — no student PII, matching the backend's
 * own deliberate design (see api/certificates.ts's docstring).
 *
 * Supports an optional `?code=` query param (pre-fills and
 * auto-submits) — this is what CertificateDetailPage.tsx's "Tekshirish"
 * link uses, via the existing react-router-dom useSearchParams hook,
 * not a new routing mechanism.
 */
import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useVerifyCertificate } from "@/hooks/useCertificates";
import { ApiError } from "@/api/client";

export function VerifyCertificatePage() {
  const [searchParams] = useSearchParams();
  const codeFromUrl = searchParams.get("code") ?? "";
  const [code, setCode] = useState(codeFromUrl);
  const verify = useVerifyCertificate();

  useEffect(() => {
    if (codeFromUrl) verify.mutate(codeFromUrl);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [codeFromUrl]);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!code.trim()) return;
    verify.mutate(code.trim());
  }

  const errorMessage =
    verify.isError && verify.error instanceof ApiError
      ? verify.error.message
      : verify.isError
        ? "Tekshirib bo'lmadi"
        : null;

  return (
    <div className="mx-auto max-w-md px-6 py-16">
      <Card>
        <CardHeader>
          <CardTitle>Sertifikatni tekshirish</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="code" className="mb-1 block text-sm font-medium text-foreground">
                Tekshiruv kodi
              </label>
              <Input
                id="code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="Kodni kiriting"
                required
              />
            </div>
            <Button type="submit" disabled={verify.isPending} className="w-full">
              {verify.isPending ? "Tekshirilmoqda..." : "Tekshirish"}
            </Button>
          </form>

          {errorMessage ? (
            <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {errorMessage}
            </div>
          ) : null}

          {verify.isSuccess ? (
            <div
              className={`mt-4 rounded-md border px-4 py-3 text-sm ${
                verify.data.is_valid ? "border-green-200 bg-green-50 text-green-700" : "border-red-200 bg-red-50 text-red-700"
              }`}
            >
              <p className="font-medium">{verify.data.is_valid ? "Sertifikat haqiqiy" : "Sertifikat haqiqiy emas"}</p>
              <p className="mt-1 font-mono text-xs">{verify.data.certificate_number}</p>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
