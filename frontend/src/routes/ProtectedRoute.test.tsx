import { describe, expect, it, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { ProtectedRoute } from "./ProtectedRoute";
import { useAuthStore } from "@/store/authStore";

function renderWithRoute(allowedPanel: "admin" | "teacher" | "student", initialPath = "/target") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/login" element={<div>Login sahifasi</div>} />
        <Route path="/admin" element={<div>Admin panel</div>} />
        <Route path="/teacher" element={<div>Teacher panel</div>} />
        <Route path="/student" element={<div>Student panel</div>} />
        <Route element={<ProtectedRoute allowedPanel={allowedPanel} />}>
          <Route path="/target" element={<div>Himoyalangan sahifa</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    useAuthStore.getState().logout(); // reset to a clean, unauthenticated state before each test
  });

  it("redirects to /login when not authenticated", () => {
    renderWithRoute("admin");
    expect(screen.getByText("Login sahifasi")).toBeInTheDocument();
  });

  it("renders the protected content when the user's role matches the allowed panel", () => {
    useAuthStore.getState().setTokens("access", "refresh");
    useAuthStore.getState().setUser({ id: "1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });

    renderWithRoute("admin");
    expect(screen.getByText("Himoyalangan sahifa")).toBeInTheDocument();
  });

  it("redirects to the user's OWN panel when their role doesn't match — never a blank screen", () => {
    useAuthStore.getState().setTokens("access", "refresh");
    useAuthStore.getState().setUser({ id: "1", first_name: "A", last_name: "B", phone: null, email: null, role: "Teacher" });

    renderWithRoute("admin"); // Teacher trying to access an admin-only route
    expect(screen.getByText("Teacher panel")).toBeInTheDocument();
  });
});
