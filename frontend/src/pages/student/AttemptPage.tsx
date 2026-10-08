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
 * Sprint 68 — `short_answer`/`essay` questions render a text field
 * (input for short_answer, textarea for essay) and save
 * `text_answer: string`. Saved on blur, not on every keystroke (see
 * handleBlurTextAnswer below) to avoid an autosave mutation storm,
 * matching this file's existing "no debounce infrastructure unless
 * genuinely required" convention. One additive backend change was
 * required and is documented at the call site: AnsweredQuestionState
 * did not return text_answer at all before this sprint, so a
 * previously typed answer could not be resumed — see
 * backend/app/modules/attempts/schemas.py's AnsweredQuestionState
 * docstring for the exact justification.
 *
 * Race condition (approved decision 2): both the Submit button and the
 * Timer's onExpire call the SAME mutation object's `.mutate()` — guarded
 * by `submitMutation.isPending` checked before either call fires, plus
 * a local ref as a synchronous belt-and-suspenders guard against the
 * rare case where two calls could otherwise land in the same tick.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/layout/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Timer } from "@/components/attempts/Timer";
import { QuestionNavigator } from "@/components/attempts/QuestionNavigator";
import { FormulaText } from "@/components/questions/FormulaText";
import { useAttempt, useModuleForAttempt, useSaveAnswer, useSubmitAndCreateResult, useSubmitModule } from "@/hooks/useAttempt";
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

  // Sprint 76 — module-aware additions. moduleId is null for a
  // non-modular attempt (attempt.module_id is null/undefined there) —
  // every hook below that depends on it is correspondingly disabled,
  // so a legacy attempt triggers none of this sprint's new requests or
  // branches (Phase 1/2 audit finding: module_id is the one reliable
  // "is this exam modular" signal the backend already provides).
  const moduleId = attempt?.module_id ?? null;
  const isModular = moduleId != null;
  const { data: moduleInfo } = useModuleForAttempt(attemptId, moduleId);
  const submitModule = useSubmitModule(attemptId ?? "");
  // Separate instance from ViewFinishedResultButton's own below — same
  // idempotent create-or-get endpoint, used here only after a modular
  // attempt's FINAL module is submitted, to resolve the real Result id
  // for navigation (mirrors fireSubmit()'s existing non-modular path,
  // which calls this same backend endpoint via useSubmitAndCreateResult).
  const resolveResultAfterFinalModule = useCreateResultForFinishedAttempt(attemptId ?? "");

  const [currentIndex, setCurrentIndex] = useState(0);
  const [confirmSubmitOpen, setConfirmSubmitOpen] = useState(false);
  const hasFiredSubmitRef = useRef(false); // synchronous guard, belt-and-suspenders alongside isPending

  // Sprint 76 — a routed module transition (submit_module's
  // next_module_id) swaps in a whole new, differently-ordered question
  // list (see Sprint 57's module-scoped question delivery) — resetting
  // to the first question avoids landing on a stale/out-of-range index
  // from the previous module. Also fires harmlessly once on initial
  // load (moduleId: undefined -> its real value), a no-op since
  // currentIndex already starts at 0.
  useEffect(() => {
    setCurrentIndex(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [moduleId]);

  // Sprint 67 (C2) — value is a single option id for single_choice/
  // true_false (unchanged), or an array of option ids for
  // multiple_choice. A multiple_choice question with no selections yet
  // has no entry with a non-empty array — it falls back to
  // selected_option, which is null for that question type, exactly
  // preserving the "unanswered" convention below.
  //
  // Sprint 68 — falls back further to text_answer (string, possibly
  // "") for short_answer/essay. Exactly one of selected_options/
  // selected_option/text_answer is ever non-null for a given question,
  // so the fallback chain never mixes values across question types.
  const answeredMap = useMemo(() => {
    const map = new Map<string, string | string[] | null>();
    attempt?.answered.forEach((a) => {
      const value =
        a.selected_options && a.selected_options.length > 0
          ? a.selected_options
          : a.text_answer ?? a.selected_option;
      map.set(a.question_id, value);
    });
    return map;
  }, [attempt]);

  // Sprint 68 — local draft for the currently-viewed short_answer/essay
  // field. Kept as component state (not derived inline) so the input
  // is a normal controlled field while typing, and only committed via
  // saveAnswer on blur — see handleBlurTextAnswer below. Re-synced from
  // the cache whenever the visible question changes (navigation or
  // initial load), which is also how a previously saved answer resumes.
  // Computed with optional chaining here (above the loading/error early
  // returns, same pattern as answeredMap above) so the hook order stays
  // stable regardless of load state.
  const currentQuestionForDraft = attempt?.questions[currentIndex];
  const [textDraft, setTextDraft] = useState("");
  useEffect(() => {
    if (!currentQuestionForDraft) return;
    const isTextType = currentQuestionForDraft.question_type === "short_answer" || currentQuestionForDraft.question_type === "essay";
    if (!isTextType) return;
    const existing = answeredMap.get(currentQuestionForDraft.id);
    setTextDraft(typeof existing === "string" ? existing : "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentQuestionForDraft?.id]);

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
  //
  // Sprint 68 — an empty/whitespace-only text_answer ("") is likewise
  // NOT "answered". selected_option is always a non-empty option id, so
  // checking for a non-empty trimmed string is safe for both that case
  // and the short_answer/essay case without needing the question_type
  // here.
  const answeredIndices = new Set(
    attempt.questions.reduce<number[]>((acc, q, i) => {
      const value = answeredMap.get(q.id);
      const isAnswered = Array.isArray(value) ? value.length > 0 : value != null && value.trim().length > 0;
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

  // Sprint 68 — commits the local draft on blur only (not per keystroke).
  // Chosen as the smallest safe implementation per this sprint's
  // instructions: it avoids a mutation storm on every keystroke while
  // adding no new infrastructure (no debounce timer, no extra library),
  // consistent with how this file already only saves on an explicit
  // user action (click) for every other question type.
  function handleBlurTextAnswer() {
    if (!currentQuestion) return;
    saveAnswer.mutate({ questionId: currentQuestion.id, textAnswer: textDraft });
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

  // Sprint 76 — the modular counterpart of fireSubmit() above, same
  // guard pattern (hasFiredSubmitRef + isPending checks, belt-and-
  // suspenders). Backend is the sole authority on what happens next
  // (Phase 3): a non-final module (completed: false) just resets the
  // guard and lets useSubmitModule's own onSuccess (useAttempt.ts)
  // invalidate the attempt-detail query — the next render picks up
  // whatever module the backend routed to, nothing is computed here. A
  // final module (completed: true) resolves the real Result id via the
  // same idempotent create-or-get endpoint fireSubmit() already uses,
  // then navigates exactly the same way.
  function fireModuleSubmit() {
    if (hasFiredSubmitRef.current || submitModule.isPending || resolveResultAfterFinalModule.isPending || !moduleId) return;
    hasFiredSubmitRef.current = true;
    submitModule.mutate(moduleId, {
      onSuccess: (outcome) => {
        if (!outcome.completed) {
          hasFiredSubmitRef.current = false;
          return;
        }
        resolveResultAfterFinalModule.mutate(undefined, {
          onSuccess: (result) => navigate(`/student/results/${result.id}`),
          onSettled: () => {
            hasFiredSubmitRef.current = false;
          },
        });
      },
      onError: () => {
        hasFiredSubmitRef.current = false;
      },
    });
  }

  function handleManualSubmitConfirm() {
    setConfirmSubmitOpen(false);
    if (isModular) {
      fireModuleSubmit();
    } else {
      fireSubmit();
    }
  }

  function handleTimerExpire() {
    // same guarded entry points as manual submit — cannot double-fire
    if (isModular) {
      fireModuleSubmit();
    } else {
      fireSubmit();
    }
  }

  // Sprint 76 — the module-scoped deadline (AttemptModuleProgress.
  // expires_at, Phase 2 audit finding, now exposed via
  // AttemptDetailOut.module_expires_at) takes priority when this is a
  // modular attempt; null/undefined falls through to the legacy
  // whole-attempt expires_at Timer already used, so a non-modular
  // attempt's Timer is byte-for-byte unchanged.
  const effectiveExpiresAt = attempt.module_expires_at ?? attempt.expires_at;
  const isSubmitPending = isModular
    ? submitModule.isPending || resolveResultAfterFinalModule.isPending
    : submitAndCreateResult.isPending;

  return (
    <div className="mx-auto max-w-3xl">
      {isModular ? (
        // Sprint 76 — module navigator (Phase 4): read-only display of
        // where the student currently is. Renders only once moduleInfo
        // has loaded (useModuleForAttempt) — until then this row is
        // simply absent, no loading skeleton invented for it.
        <div className="mb-2 text-xs text-foreground/50" data-testid="module-navigator">
          {moduleInfo ? (
            <span>
              Bo'lim {moduleInfo.section_order_number + 1}: {moduleInfo.section_name} · Modul {moduleInfo.order_number + 1}: {moduleInfo.name}
            </span>
          ) : null}
        </div>
      ) : null}
      <div className="mb-4 flex items-center justify-between border-b border-border pb-4">
        <span className="text-sm text-foreground/60">
          Savol {currentIndex + 1} / {attempt.questions.length}
        </span>
        {effectiveExpiresAt ? <Timer expiresAt={effectiveExpiresAt} onExpire={handleTimerExpire} /> : null}
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
          {/* Sprint 77 — shared stimulus/passage context for a grouped
              question (QuestionGroup.stimulus_text). Rendered from
              currentQuestion's own group_title/stimulus_text — this
              page shows exactly one question at a time, so the panel
              is naturally shown once per screen, and paging between
              two questions that share the same group_id shows the
              identical panel both times rather than it disappearing or
              being duplicated. Absent entirely for an ungrouped
              question (group_id null/undefined) or when the group has
              no stimulus_text (e.g. a diagram-only group) — nothing
              invented to fill the space. */}
          {currentQuestion.group_id && currentQuestion.stimulus_text ? (
            <div className="mb-4 rounded-md bg-foreground/5 p-4" data-testid="group-stimulus">
              {currentQuestion.group_title ? (
                // Sprint 80 — group_title is left as plain, auto-escaping
                // JSX text, NOT routed through FormulaText: unlike
                // stimulus_text/question_text/option_text, the audit
                // (Sprint 80, section 1.5) found QuestionGroup.title has
                // no backend sanitization field_validator at all (it is
                // a plain, length-bounded string, not rich-text
                // content) — rendering it via dangerouslySetInnerHTML
                // would be an unsanitized-HTML XSS surface, so it keeps
                // its pre-existing, already-safe plain-text rendering.
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-foreground/50">{currentQuestion.group_title}</p>
              ) : null}
              {/* Sprint 80 — stimulus_text is now backend-sanitized
                  (see backend/app/modules/tests/schemas.py's
                  QuestionGroupCreateRequest/UpdateRequest._stimulus_text,
                  this same sprint) and may contain $...$/$$...$$ LaTeX,
                  so it renders through the same reusable FormulaText
                  component already used for question/option text below
                  — one renderer, not a second copy of the formula logic. */}
              <FormulaText
                html={currentQuestion.stimulus_text}
                className="whitespace-pre-wrap text-sm text-foreground/80"
              />
            </div>
          ) : null}
          {/* Sprint 80 — question_text is backend-sanitized HTML
              (bleach, since Sprint 32) that may contain $...$/$$...$$
              LaTeX — previously rendered as plain JSX text, which
              both escaped the sanitized HTML back to a literal string
              AND never rendered any LaTeX. FormulaText is the existing
              reusable renderer (admin QuestionPreview.tsx) for exactly
              this contract; reused here unchanged. */}
          <FormulaText html={currentQuestion.question_text} className="mb-4 block text-foreground" />
          {currentQuestion.question_type === "short_answer" || currentQuestion.question_type === "essay" ? (
            // Sprint 68 — short_answer gets a single-line text input,
            // essay gets a multi-line textarea. Neither question type
            // has options to render (currentQuestion.options is empty
            // for both), so this branch replaces the options list
            // entirely rather than rendering alongside it.
            currentQuestion.question_type === "essay" ? (
              <textarea
                value={textDraft}
                onChange={(e) => setTextDraft(e.target.value)}
                onBlur={handleBlurTextAnswer}
                rows={6}
                placeholder="Javobingizni shu yerga yozing..."
                className="w-full rounded-md border border-border px-3 py-2 text-sm text-foreground"
              />
            ) : (
              <input
                type="text"
                value={textDraft}
                onChange={(e) => setTextDraft(e.target.value)}
                onBlur={handleBlurTextAnswer}
                placeholder="Javobingizni shu yerga yozing..."
                className="w-full rounded-md border border-border px-3 py-2 text-sm text-foreground"
              />
            )
          ) : (
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
                      {/* Sprint 80 — option_text is backend-sanitized
                          HTML (bleach, since Sprint 32) that may
                          contain $...$/$$...$$ LaTeX, same reasoning
                          as question_text above. */}
                      <FormulaText html={option.option_text} className="text-sm text-foreground" />
                    </label>
                  );
                });
              })()}
            </div>
          )}
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
        {/* Sprint 76 — isSubmitPending/submitLabel below unify the
            legacy whole-attempt submit and the new per-module submit
            under one button: which mutation is "the" pending one (and
            what the button says) depends only on isModular, computed
            once here rather than duplicating this ternary at both
            call sites below (Phase 6 — "disable submit button while
            request is pending" applies identically to both paths). */}
        <Button variant="destructive" onClick={() => setConfirmSubmitOpen(true)} disabled={isSubmitPending}>
          {isSubmitPending ? "Yuborilmoqda..." : isModular ? "Modulni yakunlash" : "Yakunlash"}
        </Button>
      </div>

      <ConfirmDialog
        open={confirmSubmitOpen}
        title={isModular ? "Modulni yakunlash" : "Testni yakunlash"}
        description={
          isModular
            ? `${attempt.questions.length - answeredIndices.size} ta savolga javob berilmagan. Ushbu modulni yakunlashni tasdiqlaysizmi? Modul yakunlangandan keyin uning savollariga qaytib bo'lmaydi.`
            : `${attempt.questions.length - answeredIndices.size} ta savolga javob berilmagan. Testni yakunlashni tasdiqlaysizmi?`
        }
        confirmLabel={isModular ? "Modulni yakunlash" : "Yakunlash"}
        isConfirming={isSubmitPending}
        onConfirm={handleManualSubmitConfirm}
        onCancel={() => setConfirmSubmitOpen(false)}
      />
    </div>
  );
}
