"""
Sprint 86 — double-submit CSRF check for the cookie-authenticated
refresh/logout endpoints.

Why this exists: once the refresh token moves to a cookie, the browser
attaches it automatically to any request to the cookie's scoped path —
including one triggered by a malicious third-party page the user merely
has open in another tab. HttpOnly stops that page's JavaScript from
*reading* the refresh token, but does nothing to stop the browser from
*sending* the cookie on a forged request. SameSite=Lax/Strict is the
first line of defense (see core/security/cookies.py), but this is a
second, explicit check per this sprint's instruction not to rely on
HttpOnly alone — defense in depth, and it degrades gracefully if a
future deployment ever needs SameSite=None.

Double-submit pattern: the non-HttpOnly `csrf_token` cookie (readable by
the frontend's own JavaScript, since it's same-origin/same-site to the
page that sets it) must be echoed back as the `X-CSRF-Token` header. A
forged cross-site request can make the browser attach the cookie
automatically, but cannot read the cookie's value to also put it in a
custom header (that would require a successful XSS, a different and
already out-of-scope threat this cannot and does not claim to defend
against) and cross-site requests cannot set arbitrary custom headers
without triggering a CORS preflight, which this app's CORS policy
(explicit ALLOWED_ORIGINS, never "*") rejects for any origin not in the
list. No server-side session/store is needed — this is a pure comparison.
"""
from fastapi import Request

from app.core.exceptions import CSRFValidationException
from app.core.security.cookies import CSRF_COOKIE_NAME, CSRF_HEADER_NAME


def verify_csrf_token(request: Request) -> None:
    cookie_value = request.cookies.get(CSRF_COOKIE_NAME)
    header_value = request.headers.get(CSRF_HEADER_NAME)

    if not cookie_value or not header_value or cookie_value != header_value:
        raise CSRFValidationException("CSRF tekshiruvi muvaffaqiyatsiz — so'rov rad etildi")
