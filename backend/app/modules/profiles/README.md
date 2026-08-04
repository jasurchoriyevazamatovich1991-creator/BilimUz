# Profiles Module — BilimUz

## Architecture

Same 8-layer pattern as every module. Reads `UserRepository` (`users`), `SchoolRepository` (`schools`), `LearningCenterRepository` (`learning_centers`) — all read-only, unmodified. One-directional dependency, same pattern `topics` already established for `subjects`/`grades`.

## ⚠️ Key design decision (Variant A, approved before implementation)

**`first_name`, `last_name`, `birth_date`, `gender`, `phone` are NOT stored on `Profile`.** They already exist on `User` (verified against `schema_v2.sql` before writing any code — `profiles` never had these columns in the first place, despite an initial request assuming otherwise). `ProfileOut.compose(user, profile)` is the **single place** these two sources are merged into one response — proven structurally by a dedicated test (`test_profile_out_has_no_duplicate_storage_fields`) asserting `ProfileOut` has exactly one `first_name` field, not two competing ones.

**This sprint is migration-free by explicit decision**: `middle_name` and `avatar_upload_id` (originally requested) don't exist in the schema and were **not added** — deferred to a future sprint rather than silently invented or built via an unapproved migration.

## Business rules

- **Lazy get-or-create**: a `Profile` row is created automatically on first access (`GET /profiles/me` or any admin lookup) if one doesn't already exist — rather than being created at registration time, which would have required modifying `auth/service.py` (stable since Sprint 4's Auth Cutover). Tested explicitly (`test_get_profile_lazily_creates_missing_profile`, and the companion test proving an *existing* profile is never recreated).
- **`school_id`/`learning_center_id` are validated against the real tables** before being stored — 422 if either doesn't reference an existing row, same read-only cross-module validation pattern as `topics` → `subjects`/`grades`.
- **A `PATCH` that doesn't touch `school_id` never queries `SchoolRepository`** — tested explicitly, confirms the validation is conditional on the field actually being present in the update, not run unconditionally on every request.
- **An orphaned profile (user_id that no longer resolves) is skipped defensively in list views**, not a crash — shouldn't happen in practice (the FK is `ON DELETE CASCADE`), but the service doesn't assume the database is always perfectly consistent.

## Database

Table: `profiles` (Module 2, `database/schema/schema_v2.sql`) — reused entirely as-is. **No schema change, no migration** (explicit approved decision — this sprint is migration-free).

## API

```
GET   /api/v1/profiles/me            — my own profile (auto-creates if missing)   Authenticated
PATCH /api/v1/profiles/me              — update my own profile                        Authenticated
GET   /api/v1/profiles                   — list, filter by school/learning_center         Super Admin
GET   /api/v1/profiles/{user_id}           — another user's profile                          Super Admin
PATCH /api/v1/profiles/{user_id}             — update another user's profile                    Super Admin
```

## RBAC — a real scope constraint, stated plainly

The original request listed **Super Admin, School Admin, Learning Center Admin, Teacher, Student** as roles needing access. **School Admin and Learning Center Admin do not exist in the current role set** (explicit approved decision: not introduced this sprint). The resulting, actually-implemented RBAC is simpler than originally envisioned:

| Access | Who |
|---|---|
| Own profile (read/write) | Any authenticated user — Teacher, Student, Admin, Super Admin all included, since it's just "yourself" |
| Another user's profile (read/write) | **Super Admin only** |

There is currently **no school-scoped or center-scoped visibility** (e.g. a School Admin seeing only their own school's students) — that tier of access control has no role to attach to yet. This is flagged here explicitly so it isn't mistaken for an oversight when `School Admin`/`Learning Center Admin` roles are eventually introduced.

## Flow — get my profile (lazy creation)

```
GET /profiles/me
  → ProfileService.get_profile(user.id)
      → user_repo.get_by_id(user.id)          [read-only, users module]
      → repo.get_by_user_id(user.id)
          → if None: create Profile(user_id=user.id), commit   [lazy creation]
      → ProfileOut.compose(user, profile)       [the one merge point]
```

## Tests

Three files, 16 tests: `test_profile_schemas.py` (3 — the composition guarantee, including the structural "no duplicate field" proof), `test_profile_service.py` (8 — not-found, lazy creation, no-recreate-if-exists, school/learning-center reference validation both rejection and success paths, conditional validation confirmed, orphaned-profile defensive skip), `test_profile_validators.py` (5 — bio length boundary, `None` handling, social-handle `@`-stripping).

## Future improvements
- `middle_name`, `avatar_upload_id` — explicitly deferred (would need a migration adding these columns to `profiles`, plus, for `avatar_upload_id`, a read-only dependency on the `uploads` module to validate the reference).
- `School Admin`/`Learning Center Admin` roles — once introduced, this module's RBAC would extend naturally: a School Admin could list/view profiles scoped to `school_id == their_own_school`, the same shape `Super Admin`'s unscoped access already has.
