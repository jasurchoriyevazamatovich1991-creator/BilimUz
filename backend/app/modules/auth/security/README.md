# Auth Security Module — `app/modules/auth/security/`

Sprint 3, Step 1: production-ready password hashing (Argon2) and structured strength validation. Self-contained — no repository/DB dependency, so `PasswordService` can be unit-tested and used anywhere without mocking.

## What's here

```
security/
├── constants.py        — policy values (min length, regex patterns, Argon2 tuning)
├── schemas.py            — PasswordValidationResult / PasswordValidationError
├── password_service.py     — PasswordService: hash_password, verify_password, validate_password_strength
├── dependencies.py           — get_password_service() (cached singleton, stateless)
└── tests/test_password_service.py
```

## Why Argon2 over bcrypt

Argon2 (specifically Argon2id, passlib's default variant) is OWASP's current recommendation for new systems: it's tunable on **memory cost**, not just time cost, which makes GPU/ASIC-parallelized cracking attempts far more expensive than bcrypt resists. `constants.py` sets `ARGON2_MEMORY_COST = 65536` (64 MB) — deliberately high enough to matter for an attacker's hardware budget, low enough to stay fast on a single login request.

## Structured validation — why not just raise on the first error

`validate_password_strength()` returns a `PasswordValidationResult` listing **every** violated rule at once (`test_all_violations_reported_at_once` in the test suite proves this). A password missing 3 of 4 requirements should tell the user all 3 in one response — not make them fix one, resubmit, discover the next, resubmit again.

## ⚠️ Known conflict — NOT YET reconciled (by design, per Sprint 3 Step 1 scope)

This module was built in isolation ("Do not continue to JWT. Stop after PasswordService is completed.") and is **not yet wired into `auth/service.py`**. The codebase currently has two parallel, inconsistent password systems:

| | Existing (Sprint 1) | New (this module) |
|---|---|---|
| Algorithm | bcrypt (`app/core/security.py`) | Argon2 |
| Location | `app/core/security.py` (mixed with JWT functions) | `app/modules/auth/security/` |
| Min length | 12 chars (`app/modules/auth/constants.py`) | 10 chars |
| Validation style | Raises `ValueError` on first failure (`app/modules/auth/validators.py`) | Returns all violations at once |
| Actually used by `auth/service.py` today | **Yes** | **No — dead code until wired in** |

**This is intentional, not an oversight** — reconciling them (retiring the old bcrypt functions, updating `auth/service.py` to use `PasswordService`, deciding whether the policy is 10 or 12 chars) is explicitly out of scope for this step and should be a deliberate follow-up, not something silently merged.

## Future improvements
- Decide and document the final password policy (10 vs 12 chars) in a single place — likely a new ADR if the answer isn't "just use this module's value."
- Wire `PasswordService` into `auth/service.py`, retiring `hash_password`/`verify_password`/`verify_verification_code`-adjacent bcrypt code from `core/security.py` (JWT functions stay there).
- If any real users exist by the time this wiring happens, add bcrypt→Argon2 migration-on-login support (`CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")` handles this natively — verify against old hash, re-hash with Argon2 on successful login).
