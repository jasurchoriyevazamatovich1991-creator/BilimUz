/**
 * Client-state store for authentication — the current user, tokens, and
 * auth status. Server state (fetching/caching `/auth/me`) belongs to
 * TanStack Query (see hooks/useAuth.ts); this store holds only what's
 * needed synchronously and outside React's render tree (the axios
 * interceptor in api/client.ts reads this via `.getState()`, not a hook).
 *
 * Token storage (Sprint 86): the ACCESS token stays here, in localStorage
 * — unchanged, since it's short-lived (15 min) and this sprint's scope is
 * the refresh token specifically. The REFRESH token is no longer stored
 * here, or anywhere JavaScript can read, at all — it now lives only in
 * the HttpOnly `refresh_token` cookie the backend sets directly (see
 * backend/app/core/security/cookies.py). This store has no
 * `refreshToken` field, no `setRefreshToken`, nothing — there is simply
 * no code path in this app that can read that value anymore. The
 * previous version of this store DID persist a `refreshToken` field;
 * `migrate()` below actively deletes it from anyone's existing
 * localStorage on first load after this upgrade, rather than leaving it
 * to sit there unused but still physically present.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface AuthUser {
  id: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  email: string | null;
  role: string;
}

interface AuthState {
  accessToken: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  setAccessToken: (accessToken: string) => void;
  setUser: (user: AuthUser) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      user: null,
      isAuthenticated: false,

      setAccessToken: (accessToken) => set({ accessToken, isAuthenticated: true }),

      setUser: (user) => set({ user }),

      logout: () => set({ accessToken: null, user: null, isAuthenticated: false }),
    }),
    {
      name: "bilimuz-auth",
      // Only persist what's needed to restore a session on page reload —
      // never persist anything beyond the access token+user, deliberately
      // narrow. No refreshToken field exists to persist any more.
      partialize: (state) => ({
        accessToken: state.accessToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
      // Sprint 86: bumps the persisted-shape version so anyone with an
      // OLDER "bilimuz-auth" localStorage entry (which had a
      // `refreshToken` field, from before this sprint) gets it stripped
      // on next load, instead of an orphaned, never-again-read refresh
      // token value sitting in localStorage indefinitely.
      version: 1,
      migrate: (persistedState) => {
        if (persistedState && typeof persistedState === "object" && "refreshToken" in persistedState) {
          const rest = { ...(persistedState as Record<string, unknown>) };
          delete rest.refreshToken;
          return rest;
        }
        return persistedState;
      },
    },
  ),
);
