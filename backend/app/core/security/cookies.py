"""
Sprint 86 — Secure refresh-token cookie helpers.

Centralizes the Set-Cookie / delete-cookie attributes for the refresh
token and its CSRF double-submit companion, so login/refresh/logout in
auth/router.py can never drift from each other (a mismatched attribute
between "set" and "clear" calls is the classic way a logout cookie fails
to actually clear in some browsers).

Two cookies are set together on login/refresh, and cleared together on
logout:

- REFRESH_TOKEN_COOKIE_NAME ("refresh_token" by default): HttpOnly, so
  frontend JavaScript can never read the refresh token — this is the
  actual security property Sprint 86 exists to deliver. Scoped to
  {API_V1_PREFIX}/auth so it is never sent to unrelated endpoints.
- "csrf_token": NOT HttpOnly (the frontend must read it and echo it back
  as a header — see core/security/csrf.py), Path="/" so it is readable
  from every frontend route. HttpOnly must never be treated as a CSRF
  defense on its own (browsers still auto-attach the refresh cookie to
  a forged cross-site request) — this second cookie is that defense.

Cookie scope note (documented here since it's easy to get wrong): cookies
are not port-scoped, so a cookie set by the backend (e.g.
http://localhost:8000) with no explicit Domain is still visible to
frontend JavaScript running on a different port of the SAME hostname
(e.g. http://localhost:5173) — this is why the dev setup works with no
extra configuration. If frontend and backend are ever deployed on
genuinely different hostnames (not just different ports of the same
host, and not subdomains of a shared registrable domain configured via
REFRESH_TOKEN_COOKIE_DOMAIN), this double-submit cookie will NOT be
readable by the frontend and the CSRF token must be delivered another
way (e.g. in the login/refresh JSON body) — see backend/README.md's
Sprint 86 section.
"""
import secrets

from fastapi import Response

from app.core.config import Settings

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _is_secure(settings: Settings) -> bool:
    # Sprint 81's own ENVIRONMENT allow-list (development/staging/production)
    # reused here rather than inventing a parallel "is this HTTPS" flag —
    # staging and production are both real, internet-reachable deployments
    # and must always get Secure=True; only local development is exempt, so
    # `npm run dev` + `uvicorn --reload` over plain HTTP keeps working.
    return settings.ENVIRONMENT != "development"


def set_refresh_token_cookies(response: Response, settings: Settings, refresh_token: str) -> str:
    """Sets both the HttpOnly refresh-token cookie and its CSRF companion.
    Returns the new CSRF token value (callers never need to return the
    refresh token itself to the frontend — see auth/schemas.py's
    AccessTokenOut, which deliberately has no refresh_token field)."""
    secure = _is_secure(settings)
    auth_path = f"{settings.API_V1_PREFIX}/auth"

    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path=auth_path,
        domain=settings.REFRESH_TOKEN_COOKIE_DOMAIN,
        secure=secure,
        httponly=True,
        samesite=settings.REFRESH_TOKEN_COOKIE_SAMESITE,
    )

    csrf_token = generate_csrf_token()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/",  # must be readable by frontend JS at every SPA route
        domain=settings.REFRESH_TOKEN_COOKIE_DOMAIN,
        secure=secure,
        httponly=False,  # the one cookie the frontend IS meant to read
        samesite=settings.REFRESH_TOKEN_COOKIE_SAMESITE,
    )
    return csrf_token


def clear_refresh_token_cookies(response: Response, settings: Settings) -> None:
    """Attributes must match set_refresh_token_cookies() exactly (path,
    domain, samesite) — a browser only deletes a cookie whose scoping
    attributes match the one being cleared; a mismatched path/domain
    silently leaves the old cookie in place instead of clearing it."""
    secure = _is_secure(settings)
    auth_path = f"{settings.API_V1_PREFIX}/auth"

    response.delete_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        path=auth_path,
        domain=settings.REFRESH_TOKEN_COOKIE_DOMAIN,
        secure=secure,
        httponly=True,
        samesite=settings.REFRESH_TOKEN_COOKIE_SAMESITE,
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        path="/",
        domain=settings.REFRESH_TOKEN_COOKIE_DOMAIN,
        secure=secure,
        httponly=False,
        samesite=settings.REFRESH_TOKEN_COOKIE_SAMESITE,
    )
