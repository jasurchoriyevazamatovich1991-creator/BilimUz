import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ErrorBoundary } from "./ErrorBoundary";

function Bomb(): never {
  throw new Error("Test render crash");
}

describe("ErrorBoundary", () => {
  it("renders children normally when there is no error", () => {
    render(
      <ErrorBoundary>
        <div>Normal kontent</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText("Normal kontent")).toBeInTheDocument();
  });

  it("renders the fallback UI instead of crashing when a child throws", () => {
    // React logs the error to console during the test — suppress noise,
    // the boundary catching it is what we're testing, not silence.
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);

    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Nimadir xato ketdi")).toBeInTheDocument();
    expect(screen.getByText("Bosh sahifaga qaytish")).toBeInTheDocument();

    consoleSpy.mockRestore();
  });
});
