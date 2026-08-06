import { describe, expect, it, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Header } from "./Header";
import { useAuthStore } from "@/store/authStore";

function renderHeader() {
  return render(
    <MemoryRouter>
      <Header />
    </MemoryRouter>,
  );
}

describe("Header", () => {
  beforeEach(() => {
    useAuthStore.getState().logout();
    useAuthStore.getState().setUser({
      id: "1",
      first_name: "Aziz",
      last_name: "Karimov",
      phone: null,
      email: null,
      role: "Teacher",
    });
  });

  it("renders nothing if there is no user", () => {
    useAuthStore.getState().logout();
    const { container } = renderHeader();
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the user's name and role badge, menu closed by default", () => {
    renderHeader();
    expect(screen.getByText("Aziz Karimov")).toBeInTheDocument();
    expect(screen.getByText("Teacher")).toBeInTheDocument();
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("opens the dropdown on click, showing Profil, Sozlamalar, and Chiqish", () => {
    renderHeader();
    fireEvent.click(screen.getByRole("button", { expanded: false }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Profil" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Sozlamalar" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Chiqish" })).toBeInTheDocument();
  });

  it("links Profil and Sozlamalar to the role-correct panel paths", () => {
    renderHeader();
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByRole("menuitem", { name: "Profil" })).toHaveAttribute("href", "/teacher/profile");
    expect(screen.getByRole("menuitem", { name: "Sozlamalar" })).toHaveAttribute("href", "/teacher/settings");
  });

  it("closes the dropdown on Escape", () => {
    renderHeader();
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("closes the dropdown on outside click", () => {
    renderHeader();
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
});
