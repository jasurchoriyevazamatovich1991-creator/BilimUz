import { beforeEach, describe, expect, it } from "vitest";
import { useAuthStore } from "./authStore";

describe("useAuthStore", () => {
  beforeEach(() => {
    useAuthStore.getState().logout();
  });

  it("has no refreshToken field on its state shape", () => {
    // Sprint 86: the whole point of this store's migration — there must
    // be no way, anywhere in this object, to read a refresh token value.
    const state = useAuthStore.getState();
    expect(state).not.toHaveProperty("refreshToken");
    expect(state).not.toHaveProperty("setTokens");
  });

  it("setAccessToken stores the access token and marks the user authenticated", () => {
    useAuthStore.getState().setAccessToken("my-access-token");
    const state = useAuthStore.getState();
    expect(state.accessToken).toBe("my-access-token");
    expect(state.isAuthenticated).toBe(true);
  });

  it("logout clears the access token and user, and does not error over a missing refresh token", () => {
    useAuthStore.getState().setAccessToken("my-access-token");
    useAuthStore.getState().setUser({
      id: "1", first_name: "A", last_name: "B", phone: null, email: null, role: "Student",
    });

    useAuthStore.getState().logout();

    const state = useAuthStore.getState();
    expect(state.accessToken).toBeNull();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
  });

  it("strips a legacy persisted refreshToken field via migrate()", () => {
    const persistOptions = (useAuthStore as unknown as {
      persist: { getOptions: () => { migrate?: (state: unknown, version: number) => unknown } };
    }).persist.getOptions();

    expect(persistOptions.migrate).toBeDefined();
    const legacyPersistedState = {
      accessToken: "old-access",
      refreshToken: "old-refresh-should-be-deleted",
      user: null,
      isAuthenticated: true,
    };

    const migrated = persistOptions.migrate!(legacyPersistedState, 0) as Record<string, unknown>;

    expect(migrated).not.toHaveProperty("refreshToken");
    expect(migrated.accessToken).toBe("old-access");
  });

  it("migrate() leaves an already-clean persisted state untouched", () => {
    const persistOptions = (useAuthStore as unknown as {
      persist: { getOptions: () => { migrate?: (state: unknown, version: number) => unknown } };
    }).persist.getOptions();

    const cleanState = { accessToken: "a", user: null, isAuthenticated: true };
    const migrated = persistOptions.migrate!(cleanState, 1);
    expect(migrated).toEqual(cleanState);
  });
});
