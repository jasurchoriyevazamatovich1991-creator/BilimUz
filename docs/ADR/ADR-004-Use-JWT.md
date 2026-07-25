# ADR-004

## Title
Use JWT (access + refresh token) for authentication

## Status
Accepted — implemented in `backend/app/auth/`

## Context
BilimUz's backend is a modular monolith today but is explicitly designed for future microservice extraction (ADR-005) and for future clients beyond the web app (Android, iOS, Telegram bot — `.cursor/context/03-roadmap.md` v3.0). Session-based auth (server-side session store keyed by cookie) would couple every future client to a shared session backend and complicate horizontal scaling of the API layer. The platform also has a hard security requirement (`.cursor/prompts/05-security.md`) for short-lived credentials and full device/session management ("Logout All Devices").

## Decision
Use **JWT access tokens** (15-minute expiry) + **JWT refresh tokens** (30-day expiry, rotated on every use, stored hashed in `refresh_tokens`), verified with `PyJWT` and a symmetric `JWT_SECRET_KEY` (HS256). No server-side session store.

## Consequences

**Positive:**
- Stateless verification — any backend instance can validate a token without a shared session store, which is required once the API is horizontally scaled behind a load balancer (`docs/00_Folder_Architecture.md`, `Internet → Load Balancer → Backend` diagram from the original project brief).
- Refresh token **rotation** (old token revoked the instant a new one is issued) limits the blast radius of a stolen refresh token — implemented and unit-tested in `auth/service.py::refresh()`.
- `logout-all` and `GET /sessions` (device management) are possible because every issued refresh token is a row in `refresh_tokens`, not an opaque, unlistable cookie.

**Negative:**
- Revoking a *still-valid access token* early (e.g. banning a user mid-session) is not instant — the access token remains valid until its 15-minute expiry. Mitigated by the short expiry itself; documented as an accepted trade-off, not silently ignored.
- Symmetric-key (HS256) signing means the same secret both signs and verifies — acceptable for a single backend service today; migrating to RS256 (asymmetric) is a documented future step if the token needs to be verified by a separate service that shouldn't be able to *issue* tokens (e.g. a future public verification microservice).

## Alternatives

| Option | Rejected because |
|---|---|
| Server-side sessions (Redis-backed) | Simpler revocation, but couples every backend instance and every future client to a shared session store; contradicts the microservices-ready goal |
| OAuth2/OIDC via a third-party IdP (Auth0, Keycloak) | Real option for the future (`OAuth 2.1 Ready` is in `.cursor/prompts/05-security.md`), but adds an external dependency and cost before the platform has proven it needs it |
| Long-lived single JWT (no refresh) | Rejected outright — violates the explicit "Short-lived Access Tokens" + "Secure Refresh Token Rotation" security requirement |

## References
- `.cursor/prompts/05-security.md`
- `backend/app/core/security.py`, `backend/app/auth/service.py`
- `backend/app/auth/README.md` (full flow diagram)
