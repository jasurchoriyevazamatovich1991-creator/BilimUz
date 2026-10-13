/**
 * Auth API module — mirrors backend/app/modules/auth/ one-to-one.
 * Every shape below was read directly from the real
 * auth/schemas.py + auth/router.py (not assumed) before writing this
 * file, so it matches the actual backend exactly, including the
 * `debug_code` field in RegisterResponse — this is a REAL, current
 * backend response shape (see README note below), not a mock.
 */
import { httpClient, unwrap } from "./client";
import { readCsrfCookie } from "@/utils/csrfCookie";

export interface RegisterRequest {
  first_name: string;
  last_name: string;
  phone: string;
  email?: string;
  password: string;
}

export interface RegisterResponse {
  user_id: string;
  /**
   * The backend currently returns the verification code directly in
   * this field instead of sending it via SMS — see
   * backend/app/modules/auth/router.py's own TODO comment
   * ("TODO(notifications module): send `plain_code` via SMS provider
   * instead of returning it"). The frontend consumes this AS-IS,
   * exactly as approved for Sprint 13 — no mock/fake SMS delivery is
   * built here to paper over it.
   */
  debug_code: string;
}

export interface VerifyRequest {
  user_id: string;
  code: string;
}

export interface LoginRequest {
  identifier: string; // phone or email
  password: string;
}

export interface AccessTokenOut {
  access_token: string;
  /**
   * Sprint 86: deliberately no `refresh_token` field here any more — the
   * backend (auth/schemas.py's AccessTokenOut) no longer puts it in the
   * response body at all. It travels only via the HttpOnly `refresh_token`
   * cookie the backend sets directly; this frontend type simply has no
   * way to represent a value it will never receive.
   */
  token_type: string;
}

export interface UserPublic {
  id: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  email: string | null;
  status: string;
  role_id: string;
  /**
   * Added to the backend's UserPublic schema specifically to unblock
   * this sprint's role-based routing — see
   * backend/app/modules/auth/schemas.py's comment on this exact field
   * for the full rationale (GET /roles/{id} is Admin-only, so the
   * frontend could not otherwise resolve role_id -> a usable name).
   */
  role: string;
}

export const authApi = {
  register: (data: RegisterRequest) => unwrap<RegisterResponse>(httpClient.post("/auth/register", data)),

  verify: (data: VerifyRequest) => unwrap<UserPublic>(httpClient.post("/auth/verify", data)),

  login: (data: LoginRequest) => unwrap<AccessTokenOut>(httpClient.post("/auth/login", data)),

  /**
   * Sprint 86: no longer takes a refresh_token argument — the backend
   * now reads it from the HttpOnly cookie the browser attaches
   * automatically (httpClient is configured with withCredentials: true,
   * see ./client.ts), not from a request body (there is no value here
   * to put in one any more). The CSRF header is attached the same way.
   */
  refresh: () =>
    unwrap<AccessTokenOut>(
      httpClient.post("/auth/refresh", null, { headers: { "X-CSRF-Token": readCsrfCookie() ?? "" } }),
    ),

  logout: () => httpClient.post("/auth/logout", null, { headers: { "X-CSRF-Token": readCsrfCookie() ?? "" } }),

  me: () => unwrap<UserPublic>(httpClient.get("/auth/me")),
};
