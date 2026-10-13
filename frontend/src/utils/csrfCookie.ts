/**
 * Sprint 86 — reads the `csrf_token` cookie the backend sets alongside
 * the HttpOnly `refresh_token` cookie (see
 * backend/app/core/security/cookies.py). This is the ONE cookie the
 * frontend is meant to read: it is deliberately NOT HttpOnly, so this
 * value can be echoed back as the `X-CSRF-Token` header on
 * cookie-authenticated requests (/auth/refresh, /auth/logout) — the
 * double-submit pattern backend/app/core/security/csrf.py checks.
 *
 * The actual refresh token itself is never readable from JavaScript at
 * all (it's HttpOnly) — there is no equivalent helper for it, by design.
 */
export function readCsrfCookie(): string | null {
  const match = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}
