/** Task 6 — calculator panel: buttons, keyboard, safe errors. */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ExamCalculator } from "./ExamCalculator";

const display = () => screen.getByTestId("calc-display");
const press = (name: string) => fireEvent.click(screen.getByRole("button", { name }));

describe("ExamCalculator", () => {
  it("computes with buttons, respecting precedence and parentheses", () => {
    render(<ExamCalculator onClose={() => {}} />);
    ["(", "1", "Qo'shish", "2", ")", "Ko'paytirish", "3", "O'nli nuqta", "5"].forEach(press);
    expect(display()).toHaveTextContent("(1+2)×3.5");
    press("Hisoblash");
    expect(display()).toHaveTextContent("10.5");
    // An operator continues from the result; a digit starts over.
    press("Bo'lish");
    press("2");
    press("Hisoblash");
    expect(display()).toHaveTextContent("5.25");
    press("9");
    expect(display()).toHaveTextContent(/^9$/);
  });

  it("supports clear and backspace", () => {
    render(<ExamCalculator onClose={() => {}} />);
    ["1", "2", "3"].forEach(press);
    press("O'chirish");
    expect(display()).toHaveTextContent("12");
    press("Tozalash");
    expect(display()).toHaveTextContent("0");
  });

  it("shows a safe message for division by zero and invalid input", () => {
    render(<ExamCalculator onClose={() => {}} />);
    ["5", "Bo'lish", "0", "Hisoblash"].forEach(press);
    expect(screen.getByRole("alert")).toHaveTextContent("Nolga bo'lib bo'lmaydi");
    expect(display()).toHaveTextContent("5÷0");
    press("Tozalash");
    ["2", "Qo'shish", "Hisoblash"].forEach(press);
    expect(screen.getByRole("alert")).toHaveTextContent("Noto'g'ri ifoda");
  });

  it("accepts keyboard input inside the panel and Escape closes it", () => {
    const onClose = vi.fn();
    render(<ExamCalculator onClose={onClose} />);
    const panel = screen.getByRole("dialog", { name: "Kalkulyator" });
    expect(panel).toHaveFocus();
    for (const key of ["1", "2", "*", "(", "3", "-", "1", ")", "Enter"]) fireEvent.keyDown(panel, { key });
    expect(display()).toHaveTextContent("24");
    fireEvent.keyDown(panel, { key: "Backspace" });
    expect(display()).toHaveTextContent(/^2$/);
    fireEvent.keyDown(panel, { key: "a" });
    expect(display()).toHaveTextContent(/^2$/);
    fireEvent.keyDown(panel, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });

  it("does not react to keys typed outside the panel", () => {
    render(
      <>
        <input aria-label="answer" />
        <ExamCalculator onClose={() => {}} />
      </>,
    );
    fireEvent.keyDown(screen.getByLabelText("answer"), { key: "7" });
    expect(display()).toHaveTextContent("0");
  });
});
