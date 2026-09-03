/**
 * Matches docs/UI-UX/ui_ux_blueprint.md §4.3's documented design
 * exactly: "raqamlar rangi bilan holat ko'rsatiladi — javob berilgan
 * (to'liq), belgilangan (bayroqcha), bo'sh (kontur). Istalgan raqamga
 * bosib o'sha savolga o'tish mumkin." Flag/bookmark state is NOT built
 * here — no backend field supports it (not in AnsweredQuestionState),
 * only answered/unanswered + current, which the backend genuinely
 * provides.
 */
interface QuestionNavigatorProps {
  totalQuestions: number;
  currentIndex: number;
  answeredIndices: Set<number>;
  onNavigate: (index: number) => void;
}

export function QuestionNavigator({ totalQuestions, currentIndex, answeredIndices, onNavigate }: QuestionNavigatorProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {Array.from({ length: totalQuestions }, (_, i) => {
        const isAnswered = answeredIndices.has(i);
        const isCurrent = i === currentIndex;
        return (
          <button
            key={i}
            type="button"
            onClick={() => onNavigate(i)}
            aria-current={isCurrent ? "step" : undefined}
            className={`flex h-9 w-9 items-center justify-center rounded-md border text-sm font-medium ${
              isCurrent
                ? "border-primary bg-primary text-primary-foreground"
                : isAnswered
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-border text-foreground/60"
            }`}
          >
            {i + 1}
          </button>
        );
      })}
    </div>
  );
}
