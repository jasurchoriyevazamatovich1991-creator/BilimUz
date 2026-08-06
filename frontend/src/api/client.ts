/**
 * Shared HTTP client — the frontend's equivalent of a backend
 * repository.py: every api/*.ts module goes through this, never
 * constructs its own axios instance. Two responsibilities live here and
 * nowhere else:
 *   1. Unwrapping the backend's single, universal response envelope
 *      ({success, message, data, errors} — core/schemas.py::success_response(),
 *      unchanged since Sprint 1).
 *   2. Silent token refresh on 401, so every other api/*.ts file can
 *      assume "if this call resolves, the user is authenticated" without
 *      re-implementing refresh logic itself.
 */
import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "@/store/authStore";

// The backend's own ALLOWED_ORIGINS (core/config.py) defaults to this
// dev port — kept in an env var so production deploys don't hardcode it.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export interface ApiEnvelope<T> {
  success: boolean;
  message: string;
  data: T;
  errors: Record<string, string[]> | null;
}

export class ApiError extends Error {
  errors: Record<string, string[]> | null;
  status: number | undefined;

  constructor(message: string, errors: Record<string, string[]> | null, status: number | undefined) {
    super(message);
    this.name = "ApiError";
    this.errors = errors;
    this.status = status;
  }
}

export const httpClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// --- Request interceptor: attach the access token ---
httpClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

// --- Response interceptor: unwrap the envelope, retry once on 401 ---
// A module-level promise, not per-request state, so concurrent 401s
// (e.g. three components fetching at once when the token just expired)
// trigger exactly ONE refresh call, not three racing ones.
let refreshPromise: Promise<string> | null = null;

async function performRefresh(): Promise<string> {
  const refreshToken = useAuthStore.getState().refreshToken;
  if (!refreshToken) throw new Error("No refresh token available");

  // Deliberately NOT using `httpClient` here — that would re-enter this
  // same interceptor if the refresh call itself ever 401s, which the
  // backend's refresh endpoint does when the refresh token is expired
  // (RateLimitExceededException/InvalidTokenException, unchanged since
  // Sprint 1) — a plain axios call avoids that recursion entirely.
  const response = await axios.post<ApiEnvelope<{ access_token: string; refresh_token: string }>>(
    `${API_BASE_URL}/auth/refresh`,
    { refresh_token: refreshToken },
  );
  const { access_token, refresh_token } = response.data.data;
  // The backend ROTATES refresh tokens on every use (unchanged since
  // Sprint 4's Auth Cutover) — the old refresh_token is now invalid,
  // so the new one must be stored, not just the new access_token.
  useAuthStore.getState().setTokens(access_token, refresh_token);
  return access_token;
}

httpClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiEnvelope<null>>) => {
    const originalRequest = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;

    const isAuthEndpoint = originalRequest?.url?.includes("/auth/login") || originalRequest?.url?.includes("/auth/refresh");

    if (error.response?.status === 401 && originalRequest && !originalRequest._retried && !isAuthEndpoint) {
      originalRequest._retried = true;
      try {
        if (!refreshPromise) {
          refreshPromise = performRefresh().finally(() => {
            refreshPromise = null;
          });
        }
        const newAccessToken = await refreshPromise;
        originalRequest.headers.set("Authorization", `Bearer ${newAccessToken}`);
        return httpClient(originalRequest);
      } catch {
        // Refresh itself failed (refresh token also expired/revoked) —
        // force logout, same as the backend treating it as unauthenticated.
        useAuthStore.getState().logout();
        return Promise.reject(new ApiError("Sessiya tugadi, qayta kiring", null, 401));
      }
    }

    const envelope = error.response?.data;
    throw new ApiError(
      envelope?.message ?? "Noma'lum xatolik yuz berdi",
      envelope?.errors ?? null,
      error.response?.status,
    );
  },
);

/** Every api/*.ts function calls this — returns `data` directly, already unwrapped. */
export async function unwrap<T>(promise: Promise<{ data: ApiEnvelope<T> }>): Promise<T> {
  const response = await promise;
  return response.data.data;
}
