/**
 * Sprint 89 — regression test for the audit finding that AppRoutes had
 * no catch-all route at all (an unknown path rendered nothing). Renders
 * the REAL AppRoutes tree (not a stub) at an unmatched path — only the
 * matched route's element actually mounts, so this does not need to
 * mock every page's API calls, just navigate somewhere nothing matches.
 */
import { describe, expect, it, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppRoutes } from "./AppRoutes";
import { useAuthStore } from "@/store/authStore";

function renderAt(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AppRoutes — catch-all / 404", () => {
  beforeEach(() => {
    useAuthStore.getState().logout();
  });

  it("renders NotFoundPage for a completely unknown path", () => {
    renderAt("/this-page-does-not-exist");
    expect(screen.getByText("404")).toBeInTheDocument();
  });

  it("renders NotFoundPage for an unknown path under a known prefix", () => {
    renderAt("/student/this-does-not-exist-either");
    // No declared route under /student matches this suffix, so React
    // Router falls through to the top-level catch-all — never a blank
    // screen, regardless of auth state.
    expect(screen.queryByText("404")).toBeInTheDocument();
  });

  it("still renders the real home page at /", () => {
    renderAt("/");
    expect(screen.queryByText("404")).not.toBeInTheDocument();
  });
});
