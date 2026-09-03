/**
 * The core test-taking screen. URL: /student/tests/:testId/attempt/:attemptId
 * (approved decision 4) — on mount, useAttempt(attemptId) fetches the
 * FULL persisted state from the backend (questions in their saved
 * order, which are already answered) — nothing is read from
 * localStorage, so a refresh always recovers correctly.
 *
 * BACKEND GAP, confirmed directly against SaveAnswerRequest before
 * writing this file: `selected_option` is a single UUID, not a list —
 * even for a `multiple_choice` question, only ONE option can be saved
 * as the answer via this endpoint. This page therefore renders single-
 * select (radio) behavior for every question, regardless of
 * question_type — not a frontend limitation, a real backend one, not
 * papered over with invented multi-select answer-saving.
 *
 * Race condition (approved decision 2): both the Submit button and the
 * Timer's onExpire call the SAME mutation object's `.mutate()` — guarded
 * by `submitMutation.isPending` checked before either call fires, plus
 * a local ref as a synchronous belt-and-suspenders guard against the
 * rare case where two calls could otherwise land in the same tick.
 */
import { useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/layout/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Timer } from "@/components/attempts/Timer";
import { QuestionNavigator } from "@/components/attempts/QuestionNavigator";
import { useAttempt, useSaveAnswer, useSubmitAndCreateResult } from "@/hooks/useAttempt";
import { useCreateResultForFinishedAttempt } from "@/hooks/useResults";

/** Small helper isolated so its own loading state doesn't affect the
 * rest of the page — resolves the real, persisted Result id (via the
 * idempotent create-or-get call) only when actually clicked. */
function ViewFinishedResultButton({ attemptId }: { attemptId: string }) {
  const navigate = useNavigate();
  const resolveResult = useCreateResultForFinishedAttempt(attemptId);

  return (
    <Button
      onClick={() => resolveResult.mutate(undefined, { onSuccess: (result) => navigate(`/student/results/${result.id}`) })}
      disabled={resolveResult.isPending}
    >
      {resolveResult.isPending ? "..." : "Natijani ko'rish"}
    </Button>
  );
}

export function AttemptPage() {
  const { testId, attemptId } = useParams<{ testId: string; attemptId: string }>();
  const navigate = useNavigate();

  const { data: attempt, isLoading, isError } = useAttempt(attemptId);
  const saveAnswer = useSaveAnswer(attemptId ?? "");
  const submitAndCreateResult = useSubmitAndCreateResult(attemptId ?? "");

  const [currentIndex, setCurrentIndex] = useState(0);
  const [confirmSubmitOpen, setConfirmSubmitOpen] = useState(false);
  const hasFiredSubmitRef = useRef(false); // synchronous guard, belt-and-suspenders alongside isPending

  const answeredMap = useMemo(() => {
    const map = new Map<string, string | null>();
    attempt?.answered.forEach((a) => map.set(a.question_id, a.selected_option));
    return map;
  }, [attempt]);

  if (!testId || !attemptId) return null;
  if (isError) return <ErrorState title="Urinish" />;
  if (isLoading || !attempt) return <p className="p-6 text-sm text-foreground/50">Yuklanmoqda...</p>;

  // The attempt already finished (submitted/auto-finished, e.g. reached
  // via a stale link or a race where expiry finished it server-side
  // between page loads) — there is nothing to take, only a result to
  // view. results.create() is idempotent (returns the existing Result
  // if one was already made), so this is safe to call again here just
  // to resolve the real result id for navigation.
  if (attempt.status !== "in_progress" && attempt.status !== "paused") {
    return (
      <div className="max-w-2xl p-6 text-center">
        <p className="mb-4 text-sm text-foreground/70">Bu urinish allaqachon yakunlangan.</p>
        <ViewFinishedResultButton attemptId={attemptId} />
      </div>
    );
  }

  const currentQuestion = attempt.questions[currentIndex];
  const answeredIndices = new Set(
    attempt.questions.reduce<number[]>((acc, q, i) => {
      if (answeredMap.get(q.id)) acc.push(i);
      return acc;
    }, []),
  );

  function handleSelectOption(optionId: string) {
    if (!currentQuestion) return;
    saveAnswer.mutate({ questionId: currentQuestion.id, selectedOption: optionId });
  }

  function fireSubmit() {
    if (hasFiredSubmitRef.current || submitAndCreateResult.isPending) return;
    hasFiredSubmitRef.current = true;
    submitAndCreateResult.mutate(undefined, {
      onSuccess: (data) => navigate(`/student/results/${data.result.id}`),
      onSettled: () => {
        hasFiredSubmitRef.current = false;
      },
    });
  }

  function handleManualSubmitConfirm() {
    setConfirmSubmitOpen(false);
    fireSubmit();
  }

  function handleTimerExpire() {
    fireSubmit(); // same guarded entry point as manual submit — cannot double-fire
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-4 flex items-center justify-between border-b border-border pb-4">
        <span className="text-sm text-foreground/60">
          Savol {currentIndex + 1} / {attempt.questions.length}
        </span>
        {attempt.expires_at ? <Timer expiresAt={attempt.expires_at} onExpire={handleTimerExpire} /> : null}
      </div>

      <div className="mb-6">
        <QuestionNavigator
          totalQuestions={attempt.questions.length}
          currentIndex={currentIndex}
          answeredIndices={answeredIndices}
          onNavigate={setCurrentIndex}
        />
      </div>

      {currentQuestion ? (
        <div className="mb-6 rounded-lg border border-border p-5">
          <p className="mb-4 text-foreground">{currentQuestion.question_text}</p>
          <div className="space-y-2">
            {currentQuestion.options.map((option) => (
              <label
                key={option.id}
                className="flex cursor-pointer items-center gap-3 rounded-md border border-border px-3 py-2 hover:bg-primary/5"
              >
                <input
                  type="radio"
                  name={`question-${currentQuestion.id}`}
                  checked={answeredMap.get(currentQuestion.id) === option.id}
                  onChange={() => handleSelectOption(option.id)}
                  disabled={saveAnswer.isPending}
                />
                <span className="text-sm text-foreground">{option.option_text}</span>
              </label>
            ))}
          </div>
        </div>
      ) : null}

      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          <button
            type="button"
            disabled={currentIndex === 0}
            onClick={() => setCurrentIndex((i) => i - 1)}
            className="rounded-md border border-border px-4 py-2 text-sm disabled:opacity-40"
          >
            Oldingi
          </button>
          <button
            type="button"
            disabled={currentIndex >= attempt.questions.length - 1}
            onClick={() => setCurrentIndex((i) => i + 1)}
            className="rounded-md border border-border px-4 py-2 text-sm disabled:opacity-40"
          >
            Keyingi
          </button>
        </div>
        <Button
          variant="destructive"
          onClick={() => setConfirmSubmitOpen(true)}
          disabled={submitAndCreateResult.isPending}
        >
          {submitAndCreateResult.isPending ? "Yuborilmoqda..." : "Yakunlash"}
        </Button>
      </div>

      <ConfirmDialog
        open={confirmSubmitOpen}
        title="Testni yakunlash"
        description={`${attempt.questions.length - answeredIndices.size} ta savolga javob berilmagan. Testni yakunlashni tasdiqlaysizmi?`}
        confirmLabel="Yakunlash"
        isConfirming={submitAndCreateResult.isPending}
        onConfirm={handleManualSubmitConfirm}
        onCancel={() => setConfirmSubmitOpen(false)}
      />
    </div>
  );
}
