import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MediaTypeBadges } from "./MediaTypeBadges";

describe("MediaTypeBadges", () => {
  it("renders a dash when there are no media items", () => {
    render(<MediaTypeBadges mediaTypes={[]} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders a badge per unique type, with the correct Uzbek label", () => {
    render(<MediaTypeBadges mediaTypes={["image", "video"]} />);
    expect(screen.getByText("Rasm")).toBeInTheDocument();
    expect(screen.getByText("Video")).toBeInTheDocument();
  });

  it("deduplicates repeated types (e.g. two images) into one badge", () => {
    render(<MediaTypeBadges mediaTypes={["image", "image"]} />);
    expect(screen.getAllByText("Rasm")).toHaveLength(1);
  });

  it("renders all four real ALLOWED_MEDIA_TYPES correctly", () => {
    render(<MediaTypeBadges mediaTypes={["image", "audio", "video", "formula"]} />);
    expect(screen.getByText("Rasm")).toBeInTheDocument();
    expect(screen.getByText("Audio")).toBeInTheDocument();
    expect(screen.getByText("Video")).toBeInTheDocument();
    expect(screen.getByText("Formula")).toBeInTheDocument();
  });
});
