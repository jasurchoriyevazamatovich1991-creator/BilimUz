/** Task 6 — question navigator state: answered and "marked for review"
 * are independent flags, combined into one of four visual states. */
export type NavigatorState = "unanswered" | "answered" | "marked" | "answered_marked";

export function navigatorState(isAnswered: boolean, isMarked: boolean): NavigatorState {
  if (isAnswered && isMarked) return "answered_marked";
  if (isMarked) return "marked";
  return isAnswered ? "answered" : "unanswered";
}
