import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { QuestionPreview } from "./QuestionPreview";

describe("QuestionPreview", () => {
  it("renders the question text and type", () => {
    render(<QuestionPreview questionText="2+2 nechi?" questionType="single_choice" options={[]} media={[]} />);
    expect(screen.getByText("2+2 nechi?")).toBeInTheDocument();
    expect(screen.getByText("single_choice")).toBeInTheDocument();
  });

  it("renders options as radio inputs for single_choice", () => {
    render(
      <QuestionPreview
        questionText="Q"
        questionType="single_choice"
        options={[{ localId: "1", option_text: "A", is_correct: true }, { localId: "2", option_text: "B", is_correct: false }]}
        media={[]}
      />,
    );
    const radios = screen.getAllByRole("radio", { hidden: true });
    expect(radios).toHaveLength(2);
  });

  it("renders options as checkboxes for multiple_choice", () => {
    render(
      <QuestionPreview
        questionText="Q"
        questionType="multiple_choice"
        options={[{ localId: "1", option_text: "A", is_correct: true }]}
        media={[]}
      />,
    );
    expect(screen.getAllByRole("checkbox", { hidden: true })).toHaveLength(1);
  });

  it("shows a text-answer placeholder for essay (no options section)", () => {
    render(<QuestionPreview questionText="Insho yozing" questionType="essay" options={[]} media={[]} />);
    expect(screen.getByText(/matn maydoni/)).toBeInTheDocument();
    expect(screen.queryByRole("radio", { hidden: true })).not.toBeInTheDocument();
  });

  it("shows question-level media, separate from option-level media", () => {
    render(
      <QuestionPreview
        questionText="Q"
        questionType="single_choice"
        options={[{ localId: "1", option_text: "A", is_correct: true }]}
        media={[{ localId: "m1", media_type: "image" }, { localId: "m2", media_type: "image", option_id: "1" }]}
      />,
    );
    // Both appear somewhere (question-level + option-level) — 2 total badges.
    expect(screen.getAllByText(/📎 image/)).toHaveLength(2);
  });

  it("renders a formula within the question text via FormulaText", () => {
    const { container } = render(<QuestionPreview questionText="$F=ma$" questionType="short_answer" options={[]} media={[]} />);
    expect(container.querySelector(".katex")).toBeInTheDocument();
  });
});
