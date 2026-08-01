# ADR-009

## Title
Auth Cutover — merge the isolated Sprint 3 Argon2/JWT track into the single production auth module

## Status
Accepted, implemented (Sprint 4)

## Context
Sprint 3 built a complete, isolated authentication track (`PasswordService` with Argon2, `JWTService` with a `nbf` claim, and Register/Login/Refresh/Me endpoints mounted at `-v2` paths) explicitly separate from the existing Sprint 1/2 auth system (bcrypt, dict-based JWT, `/auth/register` etc.), per an explicit "do not modify existing endpoints" constraint on every Sprint 3 step. This was the right way to *build and prove* the new approach without risk, but after 6 steps it produced two parallel, competing authentication systems in the same codebase — a state a user explicitly flagged as unacceptable for a production system: *"I don't want duplicate implementations. I want one clean architecture that will be used in production."*

## Decision
Merge the Sprint 3 implementation into the single, permanent auth system:

1. **`PasswordService` (Argon2) and `JWTService` (with `nbf`) move to `core/security/`** — promoted from module-local (`app/modules/auth/security/`, `app/modules/auth/jwt/`) to shared infrastructure, since JWT verification is needed by more than just the `auth` module (e.g. `permissions.require_permission()`).
2. **`app/modules/auth/service.py`, `dependencies.py`, `router.py`, `validators.py` are rewritten** to use `PasswordService`/`JWTService` instead of the original bcrypt/dict-JWT functions. Endpoint paths are unchanged (`/auth/register`, `/auth/login`, etc.) — no client-facing change.
3. **Password policy is resolved to 12 characters** (Sprint 1's original value) — Sprint 3's 10-character exploration is discarded. 12 was kept because it was the platform's already-documented security-hardening decision (`.cursor/prompts/05-security.md`), and Sprint 3 never had a stated reason to weaken it, only to demonstrate an isolated build.
4. **`app/modules/auth/security/`, `jwt/`, `registration/`, `login/`, `refresh/`, `me/` are deleted** — their logic now lives in the single `auth` module; nothing is lost, only relocated.
5. **The Sprint 3 unhandled-`pydantic.ValidationError`-on-decode fix is kept permanently** in `auth/dependencies.py`'s `get_current_user()` — this was a real robustness improvement discovered during isolated testing, not something specific to the parallel track.

## Consequences

**Positive:**
- Exactly one authentication implementation exists. `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/me` are now backed by Argon2 + typed JWT — strictly better than the pre-Sprint-3 state, with zero API surface duplication.
- `core/security/` becomes genuinely shared infrastructure — any future module needing password hashing or JWT decoding (not just `auth`) has one place to get it, consistent with how `core/` already works for config, exceptions, and middleware.
- The password policy question (10 vs 12) is answered once, not left as a standing ambiguity for a future developer to guess at.

**Negative — accepted:**
- No real users existed in any deployed database at the time of this cutover (confirmed repeatedly throughout the project), so there was no bcrypt→Argon2 migration-on-login concern to design for. **This is a one-time exemption, not a precedent**: if BilimUz reaches production with real bcrypt-hashed users before a future hashing-scheme change, that change would need a `CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")`-style migration path, not a clean swap like this one.
- The Sprint 3 step-by-step build (6 isolated modules, 6 READMEs, `-v2` paths) was real engineering effort that is now mostly deleted. This was the direct cost of building each step under a "do not integrate" constraint — the constraint was followed correctly at each step, but the *cumulative* effect (a growing, permanent-feeling parallel system) wasn't surfaced as a decision point until the user raised it. Recorded here so the same pattern is caught earlier next time a similarly-scoped multi-step build is requested.

## Alternatives

| Option | Rejected because |
|---|---|
| Keep both systems indefinitely, let clients choose | Directly contradicts the explicit requirement for one production architecture; doubles the attack surface and audit burden for zero benefit |
| Discard Sprint 3 entirely, keep bcrypt | Throws away a genuine improvement (Argon2, `nbf` claim, structured validation errors, the ValidationError-on-decode fix) for no reason — the isolated build proved the new approach worked |
| Keep `PasswordService`/`JWTService` inside `app/modules/auth/` rather than promoting to `core/` | Would work for `auth` itself, but `permissions.require_permission()` and any future module needing JWT verification would then have to import from `auth` directly, which ADR-005 established modules should not do to each other |

## References
- `docs/ADR/ADR-004-Use-JWT.md` (original JWT decision — this ADR extends it, doesn't replace it)
- `docs/ADR/ADR-005-Use-Clean-Architecture.md` (why `core/` holds shared infrastructure)
- `app/core/security/` (the merged implementation)
- `app/modules/auth/README.md` (updated module documentation)
- Sprint 3 step READMEs (`git history` — folders deleted in this cutover, content preserved via this ADR and the merged code)
