/**
 * Sprint 37: extended with real Result Analysis — correct/incorrect/
 * unanswered counts, time spent (when the attempt has a finish_time),
 * and a full question-by-question review — all sourced from
 * GET /results/{id}'s real ResultDetailOut response (no fake data).
 * The original summary card and certificate button above are
 * completely unchanged.
 */
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/layout/ErrorState";
import { useResult } from "@/hooks/useResults";
import { useTest } from "@/hooks/useTests";
import { useIssueCertificate } from "@/hooks/useCertificates";
import type { QuestionReviewOut } from "@/api/results";

function formatTimeSpent(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes} min ${remainingSeconds} sek`;
}

function QuestionReviewCard({ question, index }: { question: QuestionReviewOut; index: number }) {
  const isMultiple = question.question_type === "multiple_choice";
  const selectedIds = isMultiple ? (question.selected_options ?? []) : question.selected_option ? [question.selected_option] : [];
  const correctIds = question.options.filter((o) => o.is_correct).map((o) => o.id);
  const hasOptions = question.options.length > 0;

  let statusLabel: string;
  let statusClass: string;
  if (question.is_correct === null) {
    statusLabel = "— Javob berilmagan";
    statusClass = "bg-muted text-foreground/60";
  } else if (question.is_correct) {
    statusLabel = "✓ To'g'ri";
    statusClass = "bg-success/10 text-success";
  } else {
    statusLabel = "✗ Noto'g'ri";
    statusClass = "bg-destructive/10 text-destructive";
  }

  return (
    <div className="rounded-lg border border-border p-4">
      <div className="mb-2 flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-foreground">Savol {index + 1}: {question.question_text}</p>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${statusClass}`}>{statusLabel}</span>
      </div>

      {hasOptions ? (
        <div className="space-y-1">
          {question.options.map((option) => {
            const wasSelected = selectedIds.includes(option.id);
            const isCorrectOption = correctIds.includes(option.id);
            return (
              <p
                key={option.id}
                className={`text-sm ${isCorrectOption ? "font-medium text-success" : wasSelected ? "text-destructive" : "text-foreground/60"}`}
              >
                {wasSelected ? "→ " : ""}{option.option_text}
                {isCorrectOption ? " (to'g'ri javob)" : ""}
                {wasSelected && !isCorrectOption ? " (sizning javobingiz)" : ""}
              </p>
            );
          })}
        </div>
      ) : null}

      {question.explanation ? (
        <p className="mt-2 text-xs text-foreground/50">Izoh: {question.explanation}</p>
      ) : null}
    </div>
  );
}

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
    <div className="mx-auto max-w-xl space-y-4">
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
                result.is_passed ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive"
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

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Javoblar taqsimoti</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div>
              <p className="text-2xl font-semibold text-success">{result.correct_answers}</p>
              <p className="text-xs text-foreground/50">To'g'ri</p>
            </div>
            <div>
              <p className="text-2xl font-semibold text-destructive">{result.incorrect_answers}</p>
              <p className="text-xs text-foreground/50">Noto'g'ri</p>
            </div>
            <div>
              <p className="text-2xl font-semibold text-foreground/60">{result.unanswered}</p>
              <p className="text-xs text-foreground/50">Javobsiz</p>
            </div>
          </div>
          <p className="mt-3 text-center text-xs text-foreground/50">Jami savollar: {result.total_questions}</p>
          {result.time_spent_seconds !== null ? (
            <p className="mt-1 text-center text-xs text-foreground/50">Sarflangan vaqt: {formatTimeSpent(result.time_spent_seconds)}</p>
          ) : null}
        </CardContent>
      </Card>

      {result.questions.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Savollarni ko'rib chiqish</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {result.questions.map((question, index) => (
              <QuestionReviewCard key={question.question_id} question={question} index={index} />
            ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
