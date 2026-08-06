import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it.each(["active", "inactive", "banned", "pending_verification"])(
    "renders the '%s' status text as-is",
    (status) => {
      render(<StatusBadge status={status} />);
      expect(screen.getByText(status)).toBeInTheDocument();
    },
  );

  it("renders an unknown future status value without crashing", () => {
    render(<StatusBadge status="some_future_status" />);
    expect(screen.getByText("some_future_status")).toBeInTheDocument();
  });

  it("never renders a ban/unban action for the banned status (display-only, approved decision)", () => {
    render(<StatusBadge status="banned" />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
