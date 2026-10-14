import { describe, expect, it, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { NotFoundPage } from "./NotFoundPage";
import { useAuthStore } from "@/store/authStore";

describe("NotFoundPage", () => {
  beforeEach(() => {
    useAuthStore.getState().logout();
  });

  it("renders a 404 message", () => {
    render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("404")).toBeInTheDocument();
    expect(screen.getByText("Sahifa topilmadi")).toBeInTheDocument();
  });

  it("links to / for an unauthenticated visitor", () => {
    render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("Bosh sahifaga qaytish")).toHaveAttribute("href", "/");
  });

  it("links to the user's own panel home when authenticated", () => {
    useAuthStore.getState().setUser({ id: "1", first_name: "A", last_name: "B", phone: null, email: null, role: "Student" });
    render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("Bosh sahifaga qaytish")).toHaveAttribute("href", "/student");
  });
});
