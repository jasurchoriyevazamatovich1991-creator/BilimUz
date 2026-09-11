import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RichTextEditor } from "./RichTextEditor";

describe("RichTextEditor", () => {
  it("renders with the given aria-label and placeholder", () => {
    render(<RichTextEditor value="" onChange={vi.fn()} ariaLabel="Savol matni" placeholder="Yozing..." />);
    expect(screen.getByLabelText("Savol matni")).toBeInTheDocument();
  });

  it("calls onChange with the new HTML when the user types", () => {
    const onChange = vi.fn();
    render(<RichTextEditor value="" onChange={onChange} ariaLabel="Savol matni" />);
    const editor = screen.getByLabelText("Savol matni");
    editor.innerHTML = "Salom";
    fireEvent.input(editor);
    expect(onChange).toHaveBeenCalledWith("Salom");
  });

  it("is not editable when disabled", () => {
    render(<RichTextEditor value="" onChange={vi.fn()} ariaLabel="Savol matni" disabled />);
    expect(screen.getByLabelText("Savol matni")).not.toHaveAttribute("contenteditable", "true");
  });

  it("renders the formula toolbar button", () => {
    render(<RichTextEditor value="" onChange={vi.fn()} ariaLabel="Savol matni" />);
    expect(screen.getByTitle("Formula (LaTeX)")).toBeInTheDocument();
  });

  it("bold button applies formatting via execCommand", () => {
    // jsdom doesn't implement execCommand at all — vi.spyOn requires an
    // existing method, so a direct mock assignment is used instead.
    const execMock = vi.fn().mockReturnValue(true);
    document.execCommand = execMock;
    render(<RichTextEditor value="" onChange={vi.fn()} ariaLabel="Savol matni" />);
    fireEvent.click(screen.getByTitle("Qalin"));
    expect(execMock).toHaveBeenCalledWith("bold", false, undefined);
  });

  it("paste inserts plain text only, not rich HTML from the clipboard", () => {
    const execMock = vi.fn().mockReturnValue(true);
    document.execCommand = execMock;
    render(<RichTextEditor value="" onChange={vi.fn()} ariaLabel="Savol matni" />);
    const editor = screen.getByLabelText("Savol matni");
    const clipboardData = { getData: (type: string) => (type === "text/plain" ? "oddiy matn" : "<script>bad</script>") };
    fireEvent.paste(editor, { clipboardData });
    expect(execMock).toHaveBeenCalledWith("insertText", false, "oddiy matn");
  });
});
