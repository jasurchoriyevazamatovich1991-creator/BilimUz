/**
 * Task 2 — admin editor for a short_answer question's automatic-grading
 * configuration (IELTS gap-fill = "text", SAT grid-in / GRE numeric
 * entry = "numeric"). Controlled component: the parent form owns the
 * state and sends it with the question (see lib/shortAnswerGrading.ts).
 * Same plain-Tailwind form conventions as the rest of QuestionFormPage.
 */
import { MAX_ACCEPTED_ANSWERS, type ShortAnswerGradingState } from "@/lib/shortAnswerGrading";

interface ShortAnswerGradingFieldsProps {
  value: ShortAnswerGradingState;
  onChange: (next: ShortAnswerGradingState) => void;
  disabled?: boolean;
}

export function ShortAnswerGradingFields({ value, onChange, disabled }: ShortAnswerGradingFieldsProps) {
  const set = (patch: Partial<ShortAnswerGradingState>) => onChange({ ...value, ...patch });

  function updateAnswer(index: number, text: string) {
    set({ acceptedAnswers: value.acceptedAnswers.map((a, i) => (i === index ? text : a)) });
  }

  function removeAnswer(index: number) {
    const next = value.acceptedAnswers.filter((_, i) => i !== index);
    set({ acceptedAnswers: next.length > 0 ? next : [""] });
  }

  return (
    <fieldset className="space-y-3 rounded-md border border-border p-4" data-testid="short-answer-grading">
      <legend className="px-1 text-sm font-medium text-foreground">Avtomatik baholash</legend>

      <div>
        <label htmlFor="answerFormat" className="mb-1 block text-sm text-foreground">Javob turi</label>
        <select
          id="answerFormat"
          value={value.format}
          onChange={(e) => set({ format: e.target.value as ShortAnswerGradingState["format"] })}
          disabled={disabled}
          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm disabled:opacity-60"
        >
          <option value="">Qo'lda tekshiriladi (avtomatik baholanmaydi)</option>
          <option value="text">Matn (masalan, IELTS gap-fill)</option>
          <option value="numeric">Son (masalan, SAT grid-in, GRE numeric entry)</option>
        </select>
      </div>

      {value.format ? (
        <>
          <div>
            <span className="mb-1 block text-sm text-foreground">To'g'ri javoblar</span>
            <p className="mb-2 text-xs text-foreground/50">
              {value.format === "text"
                ? "Bir nechta qabul qilinadigan variant kiriting. Bo'shliqlar va (belgilanmasa) katta-kichik harf hisobga olinmaydi; tinish belgilari hisobga olinadi."
                : "Butun son, o'nli kasr yoki oddiy kasr: 12, 3.5, -0.25, 7/2. Vergul va 1e3 ko'rinishi qabul qilinmaydi."}
            </p>
            <div className="space-y-2">
              {value.acceptedAnswers.map((answer, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={answer}
                    onChange={(e) => updateAnswer(i, e.target.value)}
                    disabled={disabled}
                    aria-label={`To'g'ri javob ${i + 1}`}
                    inputMode={value.format === "numeric" ? "decimal" : undefined}
                    maxLength={255}
                    className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm disabled:opacity-60"
                  />
                  {!disabled ? (
                    <button
                      type="button"
                      onClick={() => removeAnswer(i)}
                      aria-label={`To'g'ri javob ${i + 1} ni o'chirish`}
                      className="text-sm text-destructive"
                    >
                      ×
                    </button>
                  ) : null}
                </div>
              ))}
            </div>
            {!disabled && value.acceptedAnswers.length < MAX_ACCEPTED_ANSWERS ? (
              <button
                type="button"
                onClick={() => set({ acceptedAnswers: [...value.acceptedAnswers, ""] })}
                className="mt-2 text-sm text-primary hover:underline"
              >
                + Javob qo'shish
              </button>
            ) : null}
          </div>

          {value.format === "text" ? (
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                checked={value.caseSensitive}
                onChange={(e) => set({ caseSensitive: e.target.checked })}
                disabled={disabled}
                className="accent-primary"
              />
              Katta-kichik harf farqlansin
            </label>
          ) : (
            <div>
              <label htmlFor="numericTolerance" className="mb-1 block text-sm text-foreground">Ruxsat etilgan farq (ixtiyoriy)</label>
              <input
                id="numericTolerance"
                type="text"
                inputMode="decimal"
                value={value.tolerance}
                onChange={(e) => set({ tolerance: e.target.value })}
                disabled={disabled}
                placeholder="0 — faqat aniq qiymat"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm disabled:opacity-60"
              />
              <p className="mt-1 text-xs text-foreground/50">
                Javob har qanday to'g'ri qiymatdan shu miqdorgacha farq qilsa ham to'g'ri hisoblanadi (chegara kiradi).
              </p>
            </div>
          )}
        </>
      ) : null}
    </fieldset>
  );
}
