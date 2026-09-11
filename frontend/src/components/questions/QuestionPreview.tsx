/**
 * Sprint 33 — renders the question editor's OWN live state (never
 * fake/mock data) approximating how a student will actually see it
 * during a test. Reuses FormulaText for safe, KaTeX-aware rendering of
 * question/option text.
 */
import { FormulaText } from "./FormulaText";

interface PreviewOption {
  localId: string;
  option_text: string;
  is_correct: boolean;
}

interface PreviewMedia {
  localId: string;
  media_type: string;
  option_id?: string;
  id?: string;
}

interface QuestionPreviewProps {
  questionText: string;
  questionType: string;
  options: PreviewOption[];
  media: PreviewMedia[];
}

export function QuestionPreview({ questionText, questionType, options, media }: QuestionPreviewProps) {
  const questionMedia = media.filter((m) => !m.option_id);
  const showOptions = ["single_choice", "multiple_choice", "true_false"].includes(questionType);
  const isSingleCorrect = questionType === "single_choice" || questionType === "true_false";

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="mb-3 text-xs uppercase tracking-wide text-foreground/50">{questionType}</p>

      <div className="mb-3 text-sm text-foreground">
        <FormulaText html={questionText || "<em>Savol matni kiritilmagan</em>"} />
      </div>

      {questionMedia.length > 0 ? (
        <div className="mb-3 flex flex-wrap gap-2">
          {questionMedia.map((m) => (
            <span key={m.localId} className="rounded border border-border bg-primary/5 px-2 py-1 text-xs text-foreground/70">
              📎 {m.media_type}
            </span>
          ))}
        </div>
      ) : null}

      {showOptions ? (
        <div className="space-y-2">
          {options.length === 0 ? (
            <p className="text-sm text-foreground/50">Hali variant qo'shilmagan</p>
          ) : (
            options.map((option) => {
              const optionMedia = media.filter((m) => m.option_id === option.localId);
              return (
                <div key={option.localId} className="flex items-start gap-2 rounded-md border border-border px-3 py-2">
                  <input type={isSingleCorrect ? "radio" : "checkbox"} disabled readOnly className="mt-1 accent-primary" aria-hidden />
                  <div className="flex-1">
                    <FormulaText html={option.option_text || "<em>Variant matni yo'q</em>"} className="text-sm text-foreground" />
                    {optionMedia.length > 0 ? (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {optionMedia.map((m) => (
                          <span key={m.localId} className="rounded bg-primary/10 px-1.5 py-0.5 text-xs text-primary">📎 {m.media_type}</span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>
              );
            })
          )}
        </div>
      ) : (
        <p className="text-sm italic text-foreground/50">
          {questionType === "essay" ? "Student javobi — matn maydoni" : "Student javobi — qisqa matn maydoni"}
        </p>
      )}
    </div>
  );
}
