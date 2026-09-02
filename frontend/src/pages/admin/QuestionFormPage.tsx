/**
 * The most complex form in the project so far. Nested under a Test
 * (/admin/tests/:testId/questions/new and .../:questionId).
 *
 * Options/Media editor (approved decision 6): ALL edits accumulate in
 * LOCAL component state. Nothing is sent to the backend until
 * "Saqlash" is clicked. On CREATE, the accumulated options are
 * submitted NESTED with the single POST /questions call (matching
 * QuestionCreateRequest exactly). On EDIT, a diff is computed against
 * the originally-loaded snapshot and executed via the granular
 * add/update/delete endpoints (hooks/useQuestions.ts's
 * useSaveQuestionOptionsAndMedia) — one real call per actual change,
 * never per keystroke.
 *
 * Validation (approved decision 7, checked on submit, never blocking
 * the button): single_choice/true_false need exactly 1 correct option;
 * multiple_choice needs at least 1. Both need >= 2 options total,
 * matching the backend's own validate_option_set exactly. essay/
 * short_answer show no options section at all (CHOICE_QUESTION_TYPES
 * gate, matches the backend).
 */
import { useState, useEffect, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/layout/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import {
  useQuestion,
  useCreateQuestion,
  useUpdateQuestion,
  useDeleteQuestion,
  useSaveQuestionOptionsAndMedia,
  type OptionsDiff,
  type MediaDiff,
} from "@/hooks/useQuestions";
import { useAuthStore } from "@/store/authStore";
import type { OptionOut, MediaOut } from "@/api/questions";

const CHOICE_TYPES = ["single_choice", "multiple_choice", "true_false"];
const MEDIA_TYPES = ["image", "audio", "video", "formula"];

interface LocalOption {
  localId: string;
  id?: string; // present only for options that already exist on the backend
  option_text: string;
  is_correct: boolean;
}

interface LocalMedia {
  localId: string;
  id?: string;
  media_type: string;
  file_url: string;
}

function newLocalId() {
  return crypto.randomUUID();
}

export function QuestionFormPage() {
  const { testId, questionId } = useParams<{ testId: string; questionId: string }>();
  const isEditMode = !!questionId;
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const canWrite = currentUser?.role === "Admin" || currentUser?.role === "Super Admin" || currentUser?.role === "Teacher";

  const { data: question, isLoading, isError } = useQuestion(questionId);
  const createQuestion = useCreateQuestion();
  const updateQuestion = useUpdateQuestion(questionId ?? "");
  const saveOptionsAndMedia = useSaveQuestionOptionsAndMedia(questionId ?? "");
  const deleteQuestion = useDeleteQuestion();

  const [questionText, setQuestionText] = useState("");
  const [questionType, setQuestionType] = useState("single_choice");
  const [difficulty, setDifficulty] = useState("medium");
  const [score, setScore] = useState(1);
  const [explanation, setExplanation] = useState("");
  const [status, setStatus] = useState("active");

  const [options, setOptions] = useState<LocalOption[]>([]);
  const [originalOptions, setOriginalOptions] = useState<OptionOut[]>([]);
  const [media, setMedia] = useState<LocalMedia[]>([]);
  const [originalMedia, setOriginalMedia] = useState<MediaOut[]>([]);

  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  useEffect(() => {
    if (question) {
      setQuestionText(question.question_text);
      setQuestionType(question.question_type);
      setDifficulty(question.difficulty);
      setScore(question.score);
      setExplanation(question.explanation ?? "");
      setStatus(question.status);
      setOriginalOptions(question.options);
      setOptions(question.options.map((o) => ({ localId: newLocalId(), id: o.id, option_text: o.option_text, is_correct: o.is_correct })));
      setOriginalMedia(question.media);
      setMedia(question.media.map((m) => ({ localId: newLocalId(), id: m.id, media_type: m.media_type, file_url: m.file_url })));
    }
  }, [question]);

  useEffect(() => {
    if (currentUser && !canWrite && !isEditMode) {
      navigate(`/admin/tests/${testId}/questions`, { replace: true });
    }
  }, [currentUser, canWrite, isEditMode, testId, navigate]);

  if (!testId) return null;
  if (!canWrite && !isEditMode) return null;
  if (isEditMode && isError) return <ErrorState title="Savol" />;
  if (isEditMode && (isLoading || !question)) return <p className="text-sm text-foreground/50">Yuklanmoqda...</p>;

  const showOptions = CHOICE_TYPES.includes(questionType);
  const isSingleCorrect = questionType === "single_choice" || questionType === "true_false";

  function addOptionRow() {
    setOptions((prev) => [...prev, { localId: newLocalId(), option_text: "", is_correct: false }]);
  }

  function removeOptionRow(localId: string) {
    setOptions((prev) => prev.filter((o) => o.localId !== localId));
  }

  function updateOptionText(localId: string, text: string) {
    setOptions((prev) => prev.map((o) => (o.localId === localId ? { ...o, option_text: text } : o)));
  }

  function toggleOptionCorrect(localId: string) {
    setOptions((prev) =>
      prev.map((o) => {
        if (isSingleCorrect) {
          // radio behavior — exactly one can be correct
          return { ...o, is_correct: o.localId === localId };
        }
        return o.localId === localId ? { ...o, is_correct: !o.is_correct } : o;
      }),
    );
  }

  function addMediaRow() {
    setMedia((prev) => [...prev, { localId: newLocalId(), media_type: "image", file_url: "" }]);
  }

  function removeMediaRow(localId: string) {
    setMedia((prev) => prev.filter((m) => m.localId !== localId));
  }

  function updateMediaField(localId: string, field: "media_type" | "file_url", value: string) {
    setMedia((prev) => prev.map((m) => (m.localId === localId ? { ...m, [field]: value } : m)));
  }

  /** Mirrors the backend's validate_option_set exactly — checked on
   * submit, never via a disabled button (approved decision 7). */
  function validateOptions(): string | null {
    if (!showOptions) return null;
    if (options.length < 2) {
      return `'${questionType}' turidagi savol kamida 2 ta variantga ega bo'lishi kerak`;
    }
    const correctCount = options.filter((o) => o.is_correct).length;
    if (isSingleCorrect && correctCount !== 1) {
      return `'${questionType}' turida aynan 1 ta to'g'ri variant bo'lishi kerak, ${correctCount} ta topildi`;
    }
    if (questionType === "multiple_choice" && correctCount < 1) {
      return "'multiple_choice' turida kamida 1 ta to'g'ri variant bo'lishi kerak";
    }
    return null;
  }

  function computeOptionsDiff(): OptionsDiff {
    const toAdd = options.filter((o) => !o.id).map((o) => ({ option_text: o.option_text, is_correct: o.is_correct }));
    const toUpdate = options
      .filter((o) => o.id)
      .filter((o) => {
        const original = originalOptions.find((orig) => orig.id === o.id);
        return original && (original.option_text !== o.option_text || original.is_correct !== o.is_correct);
      })
      .map((o) => ({ id: o.id as string, data: { option_text: o.option_text, is_correct: o.is_correct } }));
    const currentIds = new Set(options.filter((o) => o.id).map((o) => o.id));
    const toDelete = originalOptions.filter((o) => !currentIds.has(o.id)).map((o) => o.id);
    return { toAdd, toUpdate, toDelete };
  }

  function computeMediaDiff(): MediaDiff {
    const toAdd = media.filter((m) => !m.id).map((m) => ({ media_type: m.media_type, file_url: m.file_url }));
    const currentIds = new Set(media.filter((m) => m.id).map((m) => m.id));
    const toDelete = originalMedia.filter((m) => !currentIds.has(m.id)).map((m) => m.id);
    return { toAdd, toDelete };
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const validationMessage = validateOptions();
    if (validationMessage) {
      setOptionsError(validationMessage);
      return;
    }
    setOptionsError(null);

    if (isEditMode) {
      updateQuestion.mutate(
        { question_text: questionText, difficulty, score, explanation: explanation || undefined, status },
        {
          onSuccess: () => {
            saveOptionsAndMedia.mutate(
              { optionsDiff: computeOptionsDiff(), mediaDiff: computeMediaDiff() },
              { onSuccess: () => navigate(`/admin/tests/${testId}/questions/${questionId}`) },
            );
          },
        },
      );
    } else {
      createQuestion.mutate(
        {
          test_id: testId,
          question_text: questionText,
          question_type: questionType,
          difficulty,
          score,
          explanation: explanation || undefined,
          options: showOptions ? options.map((o) => ({ option_text: o.option_text, is_correct: o.is_correct })) : undefined,
        },
        { onSuccess: () => navigate(`/admin/tests/${testId}/questions`) },
      );
    }
  }

  function handleConfirmDelete() {
    if (!questionId) return;
    deleteQuestion.mutate(questionId, { onSuccess: () => navigate(`/admin/tests/${testId}/questions`) });
  }

  const isSubmitting = createQuestion.isPending || updateQuestion.isPending || saveOptionsAndMedia.isPending;

  return (
    <div className="max-w-2xl">
      <button
        type="button"
        onClick={() => navigate(`/admin/tests/${testId}/questions`)}
        className="mb-4 text-sm text-primary hover:underline"
      >
        ← Savollarga qaytish
      </button>

      <Card>
        <CardHeader>
          <CardTitle>{!canWrite ? "Savol ma'lumotlari" : isEditMode ? "Savolni tahrirlash" : "Yangi savol"}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {optionsError ? (
              <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{optionsError}</div>
            ) : null}

            <div>
              <label htmlFor="questionText" className="mb-1 block text-sm font-medium text-foreground">Savol matni</label>
              <textarea
                id="questionText"
                value={questionText}
                onChange={(e) => setQuestionText(e.target.value)}
                required
                minLength={3}
                disabled={!canWrite}
                rows={3}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm disabled:opacity-60"
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label htmlFor="questionType" className="mb-1 block text-sm font-medium text-foreground">Turi</label>
                <select
                  id="questionType"
                  value={questionType}
                  onChange={(e) => setQuestionType(e.target.value)}
                  disabled={!canWrite || isEditMode}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm disabled:opacity-60"
                >
                  <option value="single_choice">single_choice</option>
                  <option value="multiple_choice">multiple_choice</option>
                  <option value="true_false">true_false</option>
                  <option value="short_answer">short_answer</option>
                  <option value="essay">essay</option>
                </select>
                {isEditMode ? <p className="mt-1 text-xs text-foreground/50">Turi yaratilgandan keyin o'zgartirilmaydi.</p> : null}
              </div>
              <div>
                <label htmlFor="difficulty" className="mb-1 block text-sm font-medium text-foreground">Qiyinlik</label>
                <select id="difficulty" value={difficulty} onChange={(e) => setDifficulty(e.target.value)} disabled={!canWrite} className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm disabled:opacity-60">
                  <option value="easy">easy</option>
                  <option value="medium">medium</option>
                  <option value="hard">hard</option>
                </select>
              </div>
              <div>
                <label htmlFor="score" className="mb-1 block text-sm font-medium text-foreground">Ball</label>
                <Input id="score" type="number" min={0.01} step={0.01} value={score} onChange={(e) => setScore(Number(e.target.value))} disabled={!canWrite} />
              </div>
            </div>

            <div>
              <label htmlFor="explanation" className="mb-1 block text-sm font-medium text-foreground">Izoh (ixtiyoriy)</label>
              <textarea
                id="explanation"
                value={explanation}
                onChange={(e) => setExplanation(e.target.value)}
                disabled={!canWrite}
                rows={2}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm disabled:opacity-60"
              />
            </div>

            {isEditMode ? (
              <div>
                <label htmlFor="status" className="mb-1 block text-sm font-medium text-foreground">Holat</label>
                <select id="status" value={status} onChange={(e) => setStatus(e.target.value)} disabled={!canWrite} className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm disabled:opacity-60">
                  <option value="active">active</option>
                  <option value="inactive">inactive</option>
                  <option value="archived">archived</option>
                </select>
              </div>
            ) : null}

            {showOptions ? (
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-medium text-foreground">Variantlar</span>
                  {canWrite ? (
                    <button type="button" onClick={addOptionRow} className="text-sm text-primary hover:underline">
                      + Variant qo'shish
                    </button>
                  ) : null}
                </div>
                <div className="space-y-2">
                  {options.map((option) => (
                    <div key={option.localId} className="flex items-center gap-2">
                      <input
                        type={isSingleCorrect ? "radio" : "checkbox"}
                        name="correct-option"
                        checked={option.is_correct}
                        onChange={() => toggleOptionCorrect(option.localId)}
                        disabled={!canWrite}
                        aria-label="To'g'ri variant"
                      />
                      <Input
                        value={option.option_text}
                        onChange={(e) => updateOptionText(option.localId, e.target.value)}
                        placeholder="Variant matni"
                        disabled={!canWrite}
                        className="flex-1"
                      />
                      {canWrite ? (
                        <button type="button" onClick={() => removeOptionRow(option.localId)} className="text-sm text-red-600 hover:underline">
                          O'chirish
                        </button>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <div>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-medium text-foreground">Media (ixtiyoriy)</span>
                {canWrite ? (
                  <button type="button" onClick={addMediaRow} className="text-sm text-primary hover:underline">
                    + Media qo'shish
                  </button>
                ) : null}
              </div>
              <div className="space-y-2">
                {media.map((item) => (
                  <div key={item.localId} className="flex items-center gap-2">
                    <select
                      value={item.media_type}
                      onChange={(e) => updateMediaField(item.localId, "media_type", e.target.value)}
                      disabled={!canWrite}
                      className="rounded-md border border-border bg-background px-2 py-2 text-sm disabled:opacity-60"
                    >
                      {MEDIA_TYPES.map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                    <Input
                      type="url"
                      value={item.file_url}
                      onChange={(e) => updateMediaField(item.localId, "file_url", e.target.value)}
                      placeholder="https://..."
                      disabled={!canWrite}
                      className="flex-1"
                    />
                    {canWrite ? (
                      <button type="button" onClick={() => removeMediaRow(item.localId)} className="text-sm text-red-600 hover:underline">
                        O'chirish
                      </button>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>

            {canWrite ? (
              <div className="flex items-center justify-between pt-2">
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "Saqlanmoqda..." : "Saqlash"}
                </Button>
                {isEditMode ? (
                  <Button type="button" variant="destructive" onClick={() => setConfirmDeleteOpen(true)}>
                    O'chirish
                  </Button>
                ) : null}
              </div>
            ) : null}
          </form>
        </CardContent>
      </Card>

      <ConfirmDialog
        open={confirmDeleteOpen}
        title="Savolni o'chirish"
        description="Bu savol o'chirilsinmi? Bu amalni orqaga qaytarib bo'lmaydi."
        confirmLabel="O'chirish"
        isConfirming={deleteQuestion.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setConfirmDeleteOpen(false)}
      />
    </div>
  );
}
