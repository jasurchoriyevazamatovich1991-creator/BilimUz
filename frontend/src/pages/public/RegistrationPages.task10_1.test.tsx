/** Task 10.1 — public registration closed by default; no OTP shown anywhere. */
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { RegisterPage } from "./RegisterPage";
import { VerifyPage } from "./VerifyPage";
import { LoginPage } from "./LoginPage";
import { authApi } from "@/api/auth";

vi.mock("@/api/auth", async (orig) => {
  const actual = await orig<typeof import("@/api/auth")>();
  return { ...actual, authApi: { ...actual.authApi, register: vi.fn(), verify: vi.fn() } };
});

function wrap(ui: ReactNode, path = "/", state?: unknown) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[{ pathname: path, state }]}>
        <Routes>
          <Route path={path} element={ui} />
          <Route path="/verify" element={<div data-testid="verify-route">VERIFY</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllEnvs());

describe("Task 10.1 registration pages", () => {
  it("register page is closed by default and shows no form", () => {
    wrap(<RegisterPage />, "/register");
    expect(screen.getByTestId("registration-closed")).toHaveTextContent("administratoriga murojaat");
    expect(screen.queryByRole("button", { name: /ro'yxatdan/i })).not.toBeInTheDocument();
    expect(authApi.register).not.toHaveBeenCalled();
  });

  it("login page points to the administrator instead of registration by default", () => {
    wrap(<LoginPage />, "/login");
    expect(screen.getByTestId("admin-managed-accounts")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Ro'yxatdan o'ting" })).not.toBeInTheDocument();
  });

  it("when explicitly enabled, the form registers and moves to verify without any code", async () => {
    vi.stubEnv("VITE_PUBLIC_REGISTRATION_ENABLED", "true");
    vi.mocked(authApi.register).mockResolvedValue({ user_id: "u1" });
    const { container } = wrap(<RegisterPage />, "/register");
    for (const [id, value] of [["firstName", "Ali"], ["lastName", "Valiyev"], ["phone", "+998901234567"], ["password", "Strong-Pass-1234"]]) {
      fireEvent.change(container.querySelector(`#${id}`)!, { target: { value } });
    }
    fireEvent.click(container.querySelector('button[type="submit"]')!);
    await waitFor(() => expect(screen.getByTestId("verify-route")).toBeInTheDocument());
    expect(vi.mocked(authApi.register).mock.calls[0][0]).toMatchObject({ phone: "+998901234567" });
  });

  it("when explicitly enabled, the login page links to registration", () => {
    vi.stubEnv("VITE_PUBLIC_REGISTRATION_ENABLED", "true");
    wrap(<LoginPage />, "/login");
    expect(screen.getByRole("link", { name: "Ro'yxatdan o'ting" })).toBeInTheDocument();
  });

  it("verify page never displays a code, even if navigation state carries one", () => {
    wrap(<VerifyPage />, "/verify-page", { userId: "u1", debugCode: "482913" });
    expect(document.body.textContent).not.toContain("482913");
    expect(screen.getByText(/telefon raqamingizga yuboriladi/)).toBeInTheDocument();
  });
});
