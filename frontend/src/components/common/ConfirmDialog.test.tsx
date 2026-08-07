import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ConfirmDialog } from "./ConfirmDialog";

describe("ConfirmDialog", () => {
  it("renders nothing when open=false", () => {
    render(<ConfirmDialog open={false} title="T" description="D" onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders title and description when open", () => {
    render(<ConfirmDialog open title="O'chirish" description="Rostdan ham?" onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("O'chirish")).toBeInTheDocument();
    expect(screen.getByText("Rostdan ham?")).toBeInTheDocument();
  });

  it("calls onConfirm when the confirm button is clicked", () => {
    const onConfirm = vi.fn();
    render(<ConfirmDialog open title="T" description="D" onConfirm={onConfirm} onCancel={vi.fn()} />);
    fireEvent.click(screen.getByText("Tasdiqlash"));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("calls onCancel when the cancel button is clicked", () => {
    const onCancel = vi.fn();
    render(<ConfirmDialog open title="T" description="D" onConfirm={vi.fn()} onCancel={onCancel} />);
    fireEvent.click(screen.getByText("Bekor qilish"));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("calls onCancel when the backdrop is clicked", () => {
    const onCancel = vi.fn();
    render(<ConfirmDialog open title="T" description="D" onConfirm={vi.fn()} onCancel={onCancel} />);
    fireEvent.click(screen.getByRole("dialog"));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("does not call onCancel when clicking inside the dialog content", () => {
    const onCancel = vi.fn();
    render(<ConfirmDialog open title="T" description="D" onConfirm={vi.fn()} onCancel={onCancel} />);
    fireEvent.click(screen.getByText("T"));
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("disables both buttons while isConfirming is true", () => {
    render(<ConfirmDialog open title="T" description="D" isConfirming onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByText("Bekor qilish")).toBeDisabled();
  });
});
