/**
 * Sprint 89 — regression tests for the mobile nav drawer fix. jsdom
 * does not evaluate media queries, so these assert on the CLASSES that
 * drive the Tailwind breakpoint behavior (the same approach already
 * used by DashboardCard's isLoading tests elsewhere), not rendered
 * pixel positions.
 */
import { describe, expect, it, beforeEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { useUiStore } from "@/store/uiStore";

const ITEMS = [
  { label: "Dashboard", path: "/student" },
  { label: "Testlar", path: "/student/tests" },
];

function renderSidebar() {
  return render(
    <MemoryRouter>
      <Sidebar items={ITEMS} />
    </MemoryRouter>,
  );
}

describe("Sidebar — Sprint 89 mobile drawer", () => {
  beforeEach(() => {
    useUiStore.setState({ isMobileNavOpen: false });
  });

  it("is translated off-screen by default (closed)", () => {
    renderSidebar();
    expect(screen.getByText("BilimUz").closest("aside")).toHaveClass("-translate-x-full");
  });

  it("slides in when the store's isMobileNavOpen is true", () => {
    useUiStore.setState({ isMobileNavOpen: true });
    renderSidebar();
    expect(screen.getByText("BilimUz").closest("aside")).toHaveClass("translate-x-0");
  });

  it("renders a backdrop only when open", () => {
    const { rerender } = renderSidebar();
    expect(document.querySelector(".bg-black\\/40")).not.toBeInTheDocument();

    act(() => {
      useUiStore.setState({ isMobileNavOpen: true });
    });
    rerender(
      <MemoryRouter>
        <Sidebar items={ITEMS} />
      </MemoryRouter>,
    );
    expect(document.querySelector(".bg-black\\/40")).toBeInTheDocument();
  });

  it("closes when the backdrop is clicked", () => {
    useUiStore.setState({ isMobileNavOpen: true });
    renderSidebar();
    fireEvent.click(document.querySelector(".bg-black\\/40") as Element);
    expect(useUiStore.getState().isMobileNavOpen).toBe(false);
  });

  it("closes on Escape while open", () => {
    useUiStore.setState({ isMobileNavOpen: true });
    renderSidebar();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(useUiStore.getState().isMobileNavOpen).toBe(false);
  });

  it("closes after following a nav link", () => {
    useUiStore.setState({ isMobileNavOpen: true });
    renderSidebar();
    fireEvent.click(screen.getByText("Testlar"));
    expect(useUiStore.getState().isMobileNavOpen).toBe(false);
  });
});
