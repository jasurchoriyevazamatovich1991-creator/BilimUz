import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ContentBadges } from "./ContentBadges";

describe("ContentBadges", () => {
  it("renders only the badges for fields that are present", () => {
    render(<ContentBadges video="https://x.com/v" pdf={null} content={null} />);
    expect(screen.getByText("Video")).toBeInTheDocument();
    expect(screen.queryByText("PDF")).not.toBeInTheDocument();
    expect(screen.queryByText("Text")).not.toBeInTheDocument();
  });

  it("renders all three when all three are present", () => {
    render(<ContentBadges video="https://x.com/v" pdf="https://x.com/p" content="matn" />);
    expect(screen.getByText("Video")).toBeInTheDocument();
    expect(screen.getByText("PDF")).toBeInTheDocument();
    expect(screen.getByText("Text")).toBeInTheDocument();
  });

  it("renders a dash when none are present (should not happen in practice, but must not crash)", () => {
    render(<ContentBadges video={null} pdf={null} content={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
