/**
 * Shows ONLY fields the backend's real ResultOut schema provides:
 * score, percentage, is_passed, status, created_at. No per-question
 * correct/wrong breakdown — that endpoint does not exist (BACKEND GAP,
 * confirmed in the Sprint 20 audit, not invented here as a fake
 * "review your answers" section).
 *
 * Sprint 21 addition: a "Sertifikat olish" button, shown only when
 * is_passed === true, calling the real POST /certificates endpoint.
 */
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/layout/ErrorState";
import { useResult } from "@/hooks/useResults";
import { useTest } from "@/hooks/useTests";
import { useIssueCertificate } from "@/hooks/useCertificates";

export function ResultPage() {
  const { resultId } = useParams<{ resultId: string }>();
  const navigate = useNavigate();

  const { data: result, isLoading, isError } = useResult(resultId);
  const { data: test } = useTest(result?.test_id);
  const issueCertificate = useIssueCertificate();

  if (!resultId) return null;
  if (isError) return <ErrorState title="Natija" />;
  if (isLoading || !result) return <p className="p-6 text-sm text-foreground/50">Yuklanmoqda...</p>;

  function handleGetCertificate() {
    if (!result) return;
    // Idempotent on the backend — calling this again for an
    // already-certified passing result returns the existing
    // certificate rather than erroring, so no separate
    // "already have one" branch is needed here.
    issueCertificate.mutate(
      { result_id: result.id },
      { onSuccess: (certificate) => navigate(`/student/certificates/${certificate.id}`) },
    );
  }

  return (
    <div className="mx-auto max-w-xl">
      <Card>
        <CardHeader>
          <CardTitle>{test?.title ?? "Natija"}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="mb-6 text-center">
            <p className="text-4xl font-semibold text-foreground">{result.percentage}%</p>
            <p className="mt-1 text-sm text-foreground/60">{result.score} ball</p>
          </div>

          {result.is_passed !== null ? (
            <div
              className={`mb-6 rounded-md px-4 py-3 text-center text-sm font-medium ${
                result.is_passed ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
              }`}
            >
              {result.is_passed ? "O'tdingiz" : "O'ta olmadingiz"}
            </div>
          ) : null}

          <div className="flex justify-center gap-3">
            {result.is_passed === true ? (
              <Button onClick={handleGetCertificate} disabled={issueCertificate.isPending}>
                {issueCertificate.isPending ? "..." : "Sertifikat olish"}
              </Button>
            ) : null}
            <Button variant="outline" onClick={() => navigate("/student/tests")}>
              Testlarga qaytish
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
