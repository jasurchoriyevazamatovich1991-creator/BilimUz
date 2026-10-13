import { afterEach, describe, expect, it, vi } from "vitest";
import { authApi } from "./auth";
import { httpClient } from "./client";

function setCsrfCookie(value: string) {
  document.cookie = `csrf_token=${value}`;
}

function clearCsrfCookie() {
  document.cookie = "csrf_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
}

describe("authApi.refresh / authApi.logout (Sprint 86 — cookie-based refresh)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    clearCsrfCookie();
  });

  it("refresh() sends no refresh_token in the body and attaches the csrf_token cookie as X-CSRF-Token", async () => {
    setCsrfCookie("my-csrf-value");
    const postSpy = vi
      .spyOn(httpClient, "post")
      .mockResolvedValue({ data: { success: true, message: "ok", data: { access_token: "a", token_type: "bearer" }, errors: null } });

    await authApi.refresh();

    expect(postSpy).toHaveBeenCalledWith(
      "/auth/refresh",
      null,
      expect.objectContaining({ headers: { "X-CSRF-Token": "my-csrf-value" } }),
    );
    // No refresh_token anywhere in the call arguments.
    expect(JSON.stringify(postSpy.mock.calls[0])).not.toContain("refresh_token");
  });

  it("logout() sends no refresh_token in the body and attaches the csrf_token cookie as X-CSRF-Token", async () => {
    setCsrfCookie("another-csrf-value");
    const postSpy = vi.spyOn(httpClient, "post").mockResolvedValue({ status: 204 });

    await authApi.logout();

    expect(postSpy).toHaveBeenCalledWith(
      "/auth/logout",
      null,
      expect.objectContaining({ headers: { "X-CSRF-Token": "another-csrf-value" } }),
    );
    expect(JSON.stringify(postSpy.mock.calls[0])).not.toContain("refresh_token");
  });

  it("refresh() sends an empty X-CSRF-Token header when no csrf_token cookie exists, rather than throwing", async () => {
    const postSpy = vi
      .spyOn(httpClient, "post")
      .mockResolvedValue({ data: { success: true, message: "ok", data: { access_token: "a", token_type: "bearer" }, errors: null } });

    await authApi.refresh();

    expect(postSpy).toHaveBeenCalledWith("/auth/refresh", null, { headers: { "X-CSRF-Token": "" } });
  });
});
