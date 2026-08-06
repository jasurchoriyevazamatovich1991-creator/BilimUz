/**
 * TanStack Query hooks wrapping the auth API — server-state layer.
 * Client state (tokens, current user snapshot) lives in
 * store/authStore.ts; this hook is what actually TRIGGERS those
 * mutations and keeps them cache-aware, the same split described in
 * the approved architecture doc's Section 1.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { authApi, type LoginRequest, type RegisterRequest, type VerifyRequest } from "@/api/auth";
import { useAuthStore } from "@/store/authStore";
import { resolvePanel, panelBasePath } from "@/utils/roleConfig";

export function useRegister() {
  return useMutation({
    mutationFn: (data: RegisterRequest) => authApi.register(data),
  });
}

export function useVerify() {
  return useMutation({
    mutationFn: (data: VerifyRequest) => authApi.verify(data),
  });
}

export function useLogin() {
  const setTokens = useAuthStore((s) => s.setTokens);
  const setUser = useAuthStore((s) => s.setUser);
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (data: LoginRequest) => authApi.login(data),
    onSuccess: async (tokens) => {
      setTokens(tokens.access_token, tokens.refresh_token);
      // A second call is required — POST /auth/login only returns
      // tokens (TokenPair), never the user profile itself (verified
      // against the real backend router.py before writing this file).
      const me = await authApi.me();
      setUser({
        id: me.id,
        first_name: me.first_name,
        last_name: me.last_name,
        phone: me.phone,
        email: me.email,
        role: me.role,
      });
      navigate(panelBasePath(resolvePanel(me.role)), { replace: true });
    },
  });
}

export function useLogout() {
  const logout = useAuthStore((s) => s.logout);
  const refreshToken = useAuthStore((s) => s.refreshToken);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      if (refreshToken) {
        // Best-effort — even if this call fails (e.g. token already
        // expired), the local logout below still proceeds. The backend
        // revokes the refresh token server-side; a failed revoke here
        // just means it expires naturally instead.
        await authApi.logout(refreshToken).catch(() => undefined);
      }
    },
    onSettled: () => {
      logout();
      queryClient.clear();
      navigate("/login", { replace: true });
    },
  });
}

/** Restores the session on page load — if tokens exist in the
 * persisted store but `user` was somehow lost, re-fetch it. */
export function useCurrentUser() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const setUser = useAuthStore((s) => s.setUser);

  return useQuery({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      const me = await authApi.me();
      setUser({
        id: me.id,
        first_name: me.first_name,
        last_name: me.last_name,
        phone: me.phone,
        email: me.email,
        role: me.role,
      });
      return me;
    },
    enabled: isAuthenticated,
    staleTime: 5 * 60 * 1000,
    retry: false, // a 401 here means the axios interceptor already tried refreshing and failed
  });
}
