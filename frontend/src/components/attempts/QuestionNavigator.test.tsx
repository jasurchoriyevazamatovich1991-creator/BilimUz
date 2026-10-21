/** Task 6 — four navigation states (unanswered/answered/marked/both). */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { QuestionNavigator } from "./QuestionNavigator";
import { navigatorState } from "@/lib/questionNavigation";

describe("QuestionNavigator", () => {
  it("derives the state from answered + marked independently", () => {
    expect(navigatorState(false, false)).toBe("unanswered");
    expect(navigatorState(true, false)).toBe("answered");
    expect(navigatorState(false, true)).toBe("marked");
    expect(navigatorState(true, true)).toBe("answered_marked");
  });

  it("renders each state with a distinct label, flag and data-state", () => {
    const onNavigate = vi.fn();
    render(
      <QuestionNavigator totalQuestions={5} currentIndex={4} answeredIndices={new Set([1, 3])} markedIndices={new Set([2, 3])} onNavigate={onNavigate} />,
    );
    const btn = (n: number) => screen.getByRole("button", { name: new RegExp(`^Savol ${n}:`) });
    expect(btn(1)).toHaveAttribute("data-state", "unanswered");
    expect(btn(2)).toHaveAttribute("data-state", "answered");
    expect(btn(3)).toHaveAttribute("data-state", "marked");
    expect(btn(4)).toHaveAttribute("data-state", "answered_marked");
    expect(btn(3)).toHaveAccessibleName("Savol 3: ko'rib chiqish uchun belgilangan, javob berilmagan");
    expect(btn(4)).toHaveAccessibleName("Savol 4: javob berilgan, ko'rib chiqish uchun belgilangan");
    expect(screen.getAllByTestId("nav-flag")).toHaveLength(2);
    expect(btn(5)).toHaveAttribute("aria-current", "step");
    expect(screen.getByTestId("navigator-legend")).toBeInTheDocument();
    fireEvent.click(btn(3));
    expect(onNavigate).toHaveBeenCalledWith(2);
  });

  it("keeps the previous two-state rendering when no marks are passed", () => {
    render(<QuestionNavigator totalQuestions={2} currentIndex={0} answeredIndices={new Set([1])} onNavigate={() => {}} />);
    expect(screen.queryByTestId("nav-flag")).not.toBeInTheDocument();
    expect(screen.queryByTestId("navigator-legend")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Savol 2:/ })).toHaveAttribute("data-state", "answered");
  });
});
