# Auth JWT Module — `app/modules/auth/jwt/`

Sprint 3, Step 2: production-ready JWT issuance/verification. Self-contained and stateless — `JWTService` takes its secret/algorithm/expiry as constructor arguments rather than reading global settings internally, so tests use a throwaway secret with zero monkeypatching.

## What's here

```
jwt/
├── constants.py          — token-type strings, claim-name constants
├── schemas.py               — TokenType, TokenPayload (typed decode result), TokenPair
├── jwt_service.py              — JWTService: create_access_token, create_refresh_token, decode_token, verify_token_type
└── tests/test_jwt_service.py
```

## Claims

Every token carries exactly these 6 claims: `sub` (subject/user id), `jti` (unique token id — enables future revocation lookups), `type` (`access` or `refresh`), `iat` (issued-at), `nbf` (not-before — new vs. the existing `core/security.py` implementation, closes a theoretical "token valid before it was issued" gap on clock-skewed systems), `exp` (expires-at).

## `decode_token()` returns a typed object, not a dict

`TokenPayload` (Pydantic) means `payload.sub` / `payload.type` with autocomplete and type-checking, instead of `payload["sub"]` with a possible `KeyError` typo. Invalid/expired/tampered tokens raise `jwt.PyJWTError` (or a subclass like `ExpiredSignatureError`, `InvalidSignatureError`) — this method does not swallow or wrap the exception; the caller decides how to handle it, same convention as the rest of the codebase's exception handling.

## ⚠️ Known conflict — NOT YET reconciled (same situation as Step 1's PasswordService)

`app/core/security.py` already has `create_access_token()`, `create_refresh_token()`, `decode_token()`, and a `TokenType` enum — used today by `auth/service.py` for real login/refresh/logout. This new module is a **parallel, unused implementation**:

| | Existing (`core/security.py`) | New (this module) |
|---|---|---|
| Claims | `sub, type, iat, exp, jti` (no `nbf`) | `sub, jti, type, iat, nbf, exp` |
| Decode return type | raw `dict` | typed `TokenPayload` |
| Config source | reads `get_settings()` internally | constructor-injected (more testable) |
| Actually used by `auth/service.py` today | **Yes** | **No — dead code until wired in** |

Per this step's explicit scope ("Do NOT implement login/register. Do NOT modify existing auth endpoints."), no wiring was done. Reconciling this — and Step 1's password-service conflict — should happen together in a dedicated integration step, not piecemeal.

## Future improvements
- Wire `JWTService` into `auth/service.py`, retiring the JWT functions from `core/security.py` (which would then hold only non-JWT, non-password shared security concerns, if any remain).
- Add a `kid` (key ID) claim and support for key rotation if the platform ever needs to invalidate all tokens signed with an old secret without breaking already-issued valid tokens signed with a newer one.
- Consider RS256 (asymmetric) over HS256 if a future service needs to *verify* tokens without being trusted to *issue* them (e.g. a public certificate-verification microservice) — flagged already in `docs/ADR/ADR-004-Use-JWT.md`.
