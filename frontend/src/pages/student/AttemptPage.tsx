/**
 * The core test-taking screen. URL: /student/tests/:testId/attempt/:attemptId
 * (approved decision 4) — on mount, useAttempt(attemptId) fetches the
 * FULL persisted state from the backend (questions in their saved
 * order, which are already answered) — nothing is read from
 * localStorage, so a refresh always recovers correctly.
 *
 * Sprint 67 (C2) — `multiple_choice` questions render checkboxes and
 * save `selected_options: string[]`; `single_choice`/`true_false`
 * unchanged: radio buttons, `selected_option`. The backend request
 * schema (SaveAnswerRequest) has supported `selected_options` since
 * Sprint 30 — this was a frontend-only gap, not a backend one; no
 * backend file changes in this sprint.
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

  // Sprint 67 (C2) — value is a single option id for single_choice/
  // true_false (unchanged), or an array of option ids for
  // multiple_choice. A multiple_choice question with no selections yet
  // has no entry with a non-empty array — it falls back to
  // selected_option, which is null for that question type, exactly
  // preserving the "unanswered" convention below.
  const answeredMap = useMemo(() => {
    const map = new Map<string, string | string[] | null>();
    attempt?.answered.forEach((a) => {
      map.set(a.question_id, a.selected_options && a.selected_options.length > 0 ? a.selected_options : a.selected_option);
    });
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
  // Sprint 67 (C2) — an empty multiple_choice selection (`[]`) is NOT
  // "answered", matching the single_choice/true_false null convention
  // already used here. Array.isArray narrows the string | string[] |
  // null value from answeredMap above.
  const answeredIndices = new Set(
    attempt.questions.reduce<number[]>((acc, q, i) => {
      const value = answeredMap.get(q.id);
      const isAnswered = Array.isArray(value) ? value.length > 0 : value != null;
      if (isAnswered) acc.push(i);
      return acc;
    }, []),
  );

  function handleSelectOption(optionId: string) {
    if (!currentQuestion) return;
    saveAnswer.mutate({ questionId: currentQuestion.id, selectedOption: optionId });
  }

  // Sprint 67 (C2) — multiple_choice toggle: add the id if not already
  // selected, remove it if it is. Always an immutable array rebuild
  // (spread/filter), never a mutation of the existing selection.
  // KNOWN LIMITATION (documented, not fixed here — out of this sprint's
  // minimal scope): `current` is read from the query cache, which
  // useSaveAnswer only patches in onSuccess (after the request
  // resolves). Two checkbox clicks fired before the first PATCH
  // response returns would both read the same stale `current` and the
  // second click's PATCH would not include the first click's id. This
  // mirrors the existing save flow's behavior for every question type
  // (no optimistic/local-only state anywhere in this page) and was not
  // introduced by this change; fixing it (e.g. an optimistic
  // onMutate cache patch) would be a broader mutation-architecture
  // change, not the smallest change for C2.
  function handleToggleOption(optionId: string) {
    if (!currentQuestion) return;
    const current = answeredMap.get(currentQuestion.id);
    const currentIds = Array.isArray(current) ? current : [];
    const next = currentIds.includes(optionId)
      ? currentIds.filter((id) => id !== optionId)
      : [...currentIds, optionId];
    saveAnswer.mutate({ questionId: currentQuestion.id, selectedOptions: next });
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
            {(() => {
              // Sprint 67 (C2) — the only question-option rendering
              // change in this file: multiple_choice gets checkboxes and
              // an array-membership check; single_choice/true_false keep
              // the original radio-group behavior unchanged.
              const isMultiple = currentQuestion.question_type === "multiple_choice";
              const currentValue = answeredMap.get(currentQuestion.id);
              return currentQuestion.options.map((option) => {
                const isChecked = isMultiple
                  ? Array.isArray(currentValue) && currentValue.includes(option.id)
                  : currentValue === option.id;
                return (
                  <label
                    key={option.id}
                    className="flex cursor-pointer items-center gap-3 rounded-md border border-border px-3 py-2 hover:bg-primary/5"
                  >
                    <input
                      type={isMultiple ? "checkbox" : "radio"}
                      name={isMultiple ? undefined : `question-${currentQuestion.id}`}
                      checked={isChecked}
                      onChange={() => (isMultiple ? handleToggleOption(option.id) : handleSelectOption(option.id))}
                      disabled={saveAnswer.isPending}
                      className="accent-primary"
                    />
                    <span className="text-sm text-foreground">{option.option_text}</span>
                  </label>
                );
              });
            })()}
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
