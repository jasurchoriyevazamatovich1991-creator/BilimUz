# ADR-006

## Title
Use Role-Based Access Control (RBAC), with a documented path to Permission-Based Access

## Status
Accepted, partially implemented — role checks are live; the `permissions` module (fine-grained, dynamic permissions) is designed in the database but not yet built. Flagged as a "High priority" gap in the Senior Review.

## Context
BilimUz has eight distinct roles (Super Admin, Admin, Moderator, Teacher, Applicant, Student, Parent, Guest) with meaningfully different capabilities across 25 modules. The simplest correct model — checking `user.role.name` against an allowed list per endpoint — is fast to implement and easy to reason about, but doesn't handle finer needs like "this Moderator may edit *only* Mathematics and Physics" (a per-resource permission, not a per-role one).

## Decision
**v1.0**: pure RBAC — `require_roles('Admin', 'Super Admin')` as a FastAPI dependency, reused across every module's write endpoints (already the pattern in `auth` and `subjects`). The database already models the more general case (`roles`, `permissions`, `role_permissions` tables, `schema_v2.sql` Module 4) so that **v1.1's permission-based layer is additive, not a migration** — no schema change will be needed to move from role-checks to permission-checks, only new backend code in a `permissions` module.

## Consequences

**Positive:**
- Fast to build and reason about for the majority of endpoints where "only Admins can do X" is genuinely the full rule.
- Zero schema debt: when the `permissions` module is built, `require_roles(...)` calls can be replaced with `require_permission('subjects.delete')` one endpoint at a time, without a database migration, because `role_permissions` already exists and is normalized.

**Negative — accepted, not hidden:**
- Today, "Moderator scoped to specific subjects" (a named requirement in the original project brief) is **not enforceable** — a Moderator with the role checked passes `require_roles('Moderator')` for *any* subject, not just their assigned ones. This is the direct, named consequence of deferring the `permissions` module, and it blocks any endpoint that needs resource-level scoping.
- Every module built before `permissions` exists will need a follow-up pass to adopt permission checks where the business rule genuinely requires them (most CRUD-by-role endpoints will not need to change).

## Alternatives

| Option | Rejected because |
|---|---|
| Build full permission-based access before any module | Over-engineering for v1.0's actual needs — most endpoints truly are "Admin only," and building dynamic permission resolution first would have delayed `auth`/`subjects` for a capability barely used yet |
| ABAC (Attribute-Based Access Control) | Significantly more complex (policy engine, attribute resolution) than the platform's current needs justify; reconsider only if permission rules become highly contextual (e.g. time-of-day, geography) |

## References
- `.cursor/prompts/05-security.md` ("Never hardcode permissions... Every endpoint must verify permissions")
- `database/schema/schema_v2.sql` Module 4 (Permissions)
- `.cursor/context/05-system-modules.md` (Permissions: ❌ schema-only)
- Senior Review Action Plan, item 3 (High priority)
