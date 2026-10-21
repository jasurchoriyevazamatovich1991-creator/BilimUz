/**
 * Matches docs/UI-UX/ui_ux_blueprint.md §4.3's documented design:
 * "raqamlar rangi bilan holat ko'rsatiladi — javob berilgan (to'liq),
 * belgilangan (bayroqcha), bo'sh (kontur). Istalgan raqamga bosib o'sha
 * savolga o'tish mumkin."
 *
 * Task 6 — the "belgilangan" (marked for review) flag now exists on the
 * backend (AttemptDetailOut.marked_question_ids), so four states are
 * distinguished — unanswered, answered, marked, answered + marked — by
 * fill AND a flag glyph AND the aria-label (never colour alone).
 * `markedIndices` is optional so existing callers keep working.
 */
import { navigatorState, type NavigatorState } from "@/lib/questionNavigation";

interface QuestionNavigatorProps {
  totalQuestions: number;
  currentIndex: number;
  answeredIndices: Set<number>;
  markedIndices?: Set<number>;
  onNavigate: (index: number) => void;
}

const STATE_LABELS: Record<NavigatorState, string> = {
  unanswered: "javob berilmagan",
  answered: "javob berilgan",
  marked: "ko'rib chiqish uchun belgilangan, javob berilmagan",
  answered_marked: "javob berilgan, ko'rib chiqish uchun belgilangan",
};

const STATE_CLASSES: Record<NavigatorState, string> = {
  unanswered: "border-border text-foreground/60",
  answered: "border-primary/40 bg-primary/10 text-primary",
  marked: "border-amber-500 border-dashed text-amber-700",
  answered_marked: "border-amber-500 bg-primary/10 text-primary",
};

function Flag() {
  return (
    <span aria-hidden="true" data-testid="nav-flag" className="absolute -right-1 -top-1 text-[10px] leading-none text-amber-600">
      ⚑
    </span>
  );
}

export function QuestionNavigator({ totalQuestions, currentIndex, answeredIndices, markedIndices, onNavigate }: QuestionNavigatorProps) {
  const marked = markedIndices ?? new Set<number>();
  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {Array.from({ length: totalQuestions }, (_, i) => {
          const state = navigatorState(answeredIndices.has(i), marked.has(i));
          const isCurrent = i === currentIndex;
          return (
            <button
              key={i}
              type="button"
              onClick={() => onNavigate(i)}
              aria-current={isCurrent ? "step" : undefined}
              aria-label={`Savol ${i + 1}: ${STATE_LABELS[state]}`}
              data-state={state}
              className={`relative flex h-9 w-9 items-center justify-center rounded-md border text-sm font-medium ${
                isCurrent ? "border-primary bg-primary text-primary-foreground" : STATE_CLASSES[state]
              }`}
            >
              {i + 1}
              {state === "marked" || state === "answered_marked" ? <Flag /> : null}
            </button>
          );
        })}
      </div>
      {markedIndices ? (
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-foreground/60" data-testid="navigator-legend">
          <span><span className="mr-1 inline-block h-3 w-3 rounded-sm border border-border align-middle" />Javobsiz</span>
          <span><span className="mr-1 inline-block h-3 w-3 rounded-sm border border-primary/40 bg-primary/10 align-middle" />Javob berilgan</span>
          <span><span className="mr-1 text-amber-600">⚑</span>Ko'rib chiqish uchun belgilangan</span>
        </div>
      ) : null}
    </div>
  );
}
