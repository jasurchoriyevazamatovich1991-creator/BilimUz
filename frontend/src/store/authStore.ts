/**
 * Client-state store for authentication — the current user, tokens, and
 * auth status. Server state (fetching/caching `/auth/me`) belongs to
 * TanStack Query (see hooks/useAuth.ts); this store holds only what's
 * needed synchronously and outside React's render tree (the axios
 * interceptor in api/client.ts reads this via `.getState()`, not a hook).
 *
 * Token storage: localStorage (approved decision — httpOnly cookies
 * deferred to a future production-hardening sprint, since that would
 * require backend changes this sprint doesn't include). The XSS
 * exposure this implies is a known, accepted risk, not an oversight.
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
  refreshToken: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  setTokens: (accessToken: string, refreshToken: string) => void;
  setUser: (user: AuthUser) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,

      setTokens: (accessToken, refreshToken) =>
        set({ accessToken, refreshToken, isAuthenticated: true }),

      setUser: (user) => set({ user }),

      logout: () =>
        set({ accessToken: null, refreshToken: null, user: null, isAuthenticated: false }),
    }),
    {
      name: "bilimuz-auth",
      // Only persist what's needed to restore a session on page reload —
      // never persist anything beyond tokens+user, deliberately narrow.
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    },
  ),
);
