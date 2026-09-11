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
import { RichTextEditor } from "@/components/questions/RichTextEditor";
import { QuestionPreview } from "@/components/questions/QuestionPreview";
import { FileUploader } from "@/components/uploads/FileUploader";
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
import { questionsApi, type OptionOut, type MediaOut } from "@/api/questions";

const CHOICE_TYPES = ["single_choice", "multiple_choice", "true_false"];
// Sprint 33 limitation: FileUploader's onSuccess only returns the new
// upload_id, not the file's detected MIME/type — every upload here is
// tagged media_type="image" (the common case for question media).
// Selecting audio/video/formula explicitly is deferred; documented in
// the final report rather than building a guessing heuristic.

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
  upload_id?: string; // Sprint 33 — the real, R2-backed path (preferred over file_url)
  option_id?: string; // Sprint 33, Phase 6 — set when this media belongs to a specific option, not the question as a whole
}

function newLocalId() {
  return crypto.randomUUID();
}

export function QuestionFormPage({ basePath = "/admin" }: { basePath?: string }) {
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
  const [showPreview, setShowPreview] = useState(false);

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
      setMedia(
        question.media.map((m) => ({
          localId: newLocalId(), id: m.id, media_type: m.media_type, file_url: m.file_url,
          upload_id: m.upload_id ?? undefined, option_id: m.option_id ?? undefined,
        })),
      );
    }
  }, [question]);

  useEffect(() => {
    if (currentUser && !canWrite && !isEditMode) {
      navigate(`${basePath}/tests/${testId}/questions`, { replace: true });
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

  function handleMediaUploaded(uploadId: string, mediaType: string, optionId?: string) {
    setMedia((prev) => [...prev, { localId: newLocalId(), media_type: mediaType, file_url: "", upload_id: uploadId, option_id: optionId }]);
  }

  function removeMediaRow(localId: string) {
    setMedia((prev) => prev.filter((m) => m.localId !== localId));
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
    const toAdd = media
      .filter((m) => !m.id)
      .map((m) => ({ media_type: m.media_type, upload_id: m.upload_id, file_url: m.upload_id ? undefined : m.file_url, option_id: m.option_id }));
    const currentIds = new Set(media.filter((m) => m.id).map((m) => m.id));
    const toDelete = originalMedia.filter((m) => !currentIds.has(m.id)).map((m) => m.id);
    return { toAdd, toDelete };
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    // testId is already guaranteed non-null by the component-level guard
    // (line 111), but that narrowing doesn't propagate into this nested
    // closure for TypeScript's static analysis — re-asserted explicitly
    // here rather than a blind `!`, since this is the actual point test_id
    // is used (only on the create branch below).
    if (!testId) return;

    // RichTextEditor is a contentEditable div, not a native form input —
    // it doesn't participate in the browser's own `required` validation
    // (which the original plain <textarea> relied on), so this check
    // replaces that lost behavior explicitly.
    const plainQuestionText = questionText.replace(/<[^>]*>/g, "").trim();
    if (plainQuestionText.length < 3) {
      setOptionsError("Savol matni kamida 3 belgidan iborat bo'lishi kerak");
      return;
    }

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
              { onSuccess: () => navigate(`${basePath}/tests/${testId}/questions/${questionId}`) },
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
        {
          onSuccess: async (createdQuestion) => {
            // QuestionCreateRequest has no nested media field (verified
            // against the real backend schema) — any media staged
            // before the question existed is applied here, directly,
            // using the question's real new id. Sequential (not
            // parallel), same reasoning as useSaveQuestionOptionsAndMedia.
            for (const m of media) {
              await questionsApi.addMedia(createdQuestion.id, {
                media_type: m.media_type, upload_id: m.upload_id, option_id: m.option_id,
              });
            }
            navigate(`${basePath}/tests/${testId}/questions`);
          },
        },
      );
    }
  }

  function handleConfirmDelete() {
    if (!questionId) return;
    deleteQuestion.mutate(questionId, { onSuccess: () => navigate(`${basePath}/tests/${testId}/questions`) });
  }

  const isSubmitting = createQuestion.isPending || updateQuestion.isPending || saveOptionsAndMedia.isPending;

  return (
    <div className="max-w-2xl">
      <button
        type="button"
        onClick={() => navigate(`${basePath}/tests/${testId}/questions`)}
        className="mb-4 text-sm text-primary hover:underline"
      >
        ← Savollarga qaytish
      </button>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>{!canWrite ? "Savol ma'lumotlari" : isEditMode ? "Savolni tahrirlash" : "Yangi savol"}</CardTitle>
          <button type="button" onClick={() => setShowPreview((p) => !p)} className="text-sm text-primary hover:underline">
            {showPreview ? "Tahrirlashga qaytish" : "Ko'rib chiqish (Preview)"}
          </button>
        </CardHeader>
        <CardContent>
          {showPreview ? (
            <QuestionPreview
              questionText={questionText}
              questionType={questionType}
              options={options}
              media={media}
            />
          ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {optionsError ? (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 text-destructive">{optionsError}</div>
            ) : null}

            <div>
              <label className="mb-1 block text-sm font-medium text-foreground">Savol matni</label>
              <RichTextEditor
                value={questionText}
                onChange={setQuestionText}
                placeholder="Savol matnini kiriting..."
                ariaLabel="Savol matni"
                disabled={!canWrite}
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
              <label className="mb-1 block text-sm font-medium text-foreground">Izoh (ixtiyoriy)</label>
              <RichTextEditor
                value={explanation}
                onChange={setExplanation}
                placeholder="Izoh (ixtiyoriy)..."
                ariaLabel="Izoh"
                disabled={!canWrite}
                minHeightClassName="min-h-[80px]"
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
                <div className="space-y-3">
                  {options.map((option, index) => {
                    const optionMedia = option.id ? media.filter((m) => m.option_id === option.id) : [];
                    return (
                      <div key={option.localId} className="rounded-md border border-border p-2">
                        <div className="flex items-center gap-2">
                          <input
                            type={isSingleCorrect ? "radio" : "checkbox"}
                            name="correct-option"
                            checked={option.is_correct}
                            onChange={() => toggleOptionCorrect(option.localId)}
                            disabled={!canWrite}
                            aria-label="To'g'ri variant"
                            className="accent-primary"
                          />
                          <div className="flex-1">
                            <RichTextEditor
                              value={option.option_text}
                              onChange={(html) => updateOptionText(option.localId, html)}
                              placeholder="Variant matni"
                              ariaLabel={`Variant matni ${index + 1}`}
                              disabled={!canWrite}
                              minHeightClassName="min-h-[44px]"
                            />
                          </div>
                          {canWrite ? (
                            <button type="button" onClick={() => removeOptionRow(option.localId)} className="text-sm text-destructive hover:underline">
                              O'chirish
                            </button>
                          ) : null}
                        </div>
                        {optionMedia.length > 0 ? (
                          <div className="mt-2 flex flex-wrap gap-2 pl-7">
                            {optionMedia.map((m) => (
                              <span key={m.localId} className="rounded bg-primary/10 px-2 py-1 text-xs text-primary">
                                {m.media_type} {canWrite ? (
                                  <button type="button" onClick={() => removeMediaRow(m.localId)} className="ml-1 text-destructive">×</button>
                                ) : null}
                              </span>
                            ))}
                          </div>
                        ) : null}
                        {canWrite && option.id ? (
                          <div className="mt-2 pl-7">
                            <FileUploader onSuccess={(uploadId) => handleMediaUploaded(uploadId, "image", option.id)} />
                          </div>
                        ) : canWrite ? (
                          <p className="mt-2 pl-7 text-xs text-foreground/50">
                            Rasm biriktirish uchun avval variantni saqlang.
                          </p>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : null}

            <div>
              <span className="mb-2 block text-sm font-medium text-foreground">Savol mediasi (ixtiyoriy)</span>
              <div className="mb-2 flex flex-wrap gap-2">
                {media.filter((m) => !m.option_id).map((item) => (
                  <span key={item.localId} className="rounded bg-primary/10 px-2 py-1 text-xs text-primary">
                    {item.media_type} {canWrite ? (
                      <button type="button" onClick={() => removeMediaRow(item.localId)} className="ml-1 text-destructive">×</button>
                    ) : null}
                  </span>
                ))}
              </div>
              {canWrite ? (
                <FileUploader onSuccess={(uploadId) => handleMediaUploaded(uploadId, "image")} />
              ) : null}
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
          )}
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
