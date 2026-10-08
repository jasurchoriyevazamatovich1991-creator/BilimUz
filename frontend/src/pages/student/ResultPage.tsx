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
import type { QuestionReviewOut, ResultSectionOut } from "@/api/results";
import { FormulaText } from "@/components/questions/FormulaText";

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
  // Sprint 70 — short_answer/essay submissions are never auto-graded, so
  // is_correct stays null for them even when the student answered.
  // text_answer (trimmed, matching Sprint 68's AttemptPage convention)
  // is what tells a genuinely-unanswered question apart from an
  // answered-but-ungraded one; this check must run before the
  // is_correct === null branch below, or a submitted answer would be
  // shown as "Javob berilmagan".
  const hasTextAnswer = (question.text_answer ?? "").trim().length > 0;

  let statusLabel: string;
  let statusClass: string;
  if (hasTextAnswer) {
    statusLabel = "Javob berildi";
    statusClass = "bg-muted text-foreground/60";
  } else if (question.is_correct === null) {
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
      {/* Sprint 80 — shared stimulus/passage context for a grouped
          question, mirroring AttemptPage's identical Sprint 77 panel
          (and its Sprint 80 FormulaText wiring) exactly — same
          "absent entirely when ungrouped or group has no stimulus_text"
          rule. group_title stays plain JSX text, NOT FormulaText: the
          audit found QuestionGroup.title has no backend sanitization
          (it's a plain, length-bounded string, not rich-text content),
          so routing it through dangerouslySetInnerHTML would be an
          unsanitized-HTML XSS surface. */}
      {question.group_id && question.stimulus_text ? (
        <div className="mb-3 rounded-md bg-foreground/5 p-3" data-testid="group-stimulus">
          {question.group_title ? (
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-foreground/50">{question.group_title}</p>
          ) : null}
          <FormulaText html={question.stimulus_text} className="whitespace-pre-wrap text-sm text-foreground/80" />
        </div>
      ) : null}

      <div className="mb-2 flex items-start justify-between gap-2">
        {/* Sprint 80 — question_text is backend-sanitized HTML (bleach)
            that may contain $...$/$$...$$ LaTeX; reuses the same
            FormulaText component AttemptPage uses, not a second
            rendering implementation. */}
        <p className="text-sm font-medium text-foreground">
          Savol {index + 1}: <FormulaText html={question.question_text} />
        </p>
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
                {wasSelected ? "→ " : ""}
                {/* Sprint 80 — option_text is backend-sanitized HTML,
                    same reasoning as question_text above. */}
                <FormulaText html={option.option_text} />
                {isCorrectOption ? " (to'g'ri javob)" : ""}
                {wasSelected && !isCorrectOption ? " (sizning javobingiz)" : ""}
              </p>
            );
          })}
        </div>
      ) : null}

      {hasTextAnswer ? (
        // Sprint 80 — text_answer is the student's OWN typed free text
        // (short_answer/essay), NEVER passed through sanitize_rich_text
        // server-side (confirmed by audit: save_answer()'s free-text
        // branch persists it verbatim). It must stay plain, auto-
        // escaping JSX — routing it through FormulaText's
        // dangerouslySetInnerHTML would introduce a brand-new XSS
        // vector that does not exist today.
        <p className="text-sm text-foreground/80">Javobingiz: {question.text_answer}</p>
      ) : null}

      {question.explanation ? (
        // Sprint 80 — explanation already had its own dedicated
        // sanitize_rich_text field_validator since Sprint 32
        // specifically because it is rendered here, during result
        // review — same FormulaText reuse as above.
        <p className="mt-2 text-xs text-foreground/50">
          Izoh: <FormulaText html={question.explanation} />
        </p>
      ) : null}
    </div>
  );
}

/** Sprint 73 — RS-FE-1. Backend has produced correctly-scoped
 * `ResultSectionOut` rows since Sprint 72 (RS-1) for every modular
 * test, but the frontend never consumed them — this renders the
 * per-section score list the backend already orders correctly.
 * `raw_score`/`scaled_score` are both nullable (e.g. a section whose
 * questions are all manual-grading types scores null, not 0 — see
 * backend Sprint 72 RS1-D), rendered as "—" rather than "null"/"0". */
function SectionScoreRow({ section, index }: { section: ResultSectionOut; index: number }) {
  const label = section.name ?? `Bo'lim ${index + 1}`;
  const scoreText = section.raw_score === null ? "—" : `${section.raw_score} ball`;
  return (
    <div className="flex items-center justify-between border-b border-border py-2 text-sm last:border-0">
      <span className="text-foreground">{label}</span>
      <span className="font-medium text-foreground/80">{scoreText}</span>
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

      {result.sections.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Bo'limlar bo'yicha natija</CardTitle>
          </CardHeader>
          <CardContent>
            {result.sections.map((section, index) => (
              <SectionScoreRow key={section.id} section={section} index={index} />
            ))}
          </CardContent>
        </Card>
      ) : null}

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
