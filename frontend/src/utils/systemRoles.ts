/**
 * Mirrors backend/app/modules/roles/constants.py's SYSTEM_ROLE_NAMES
 * EXACTLY (verified directly against the source before writing this
 * file — not guessed). These 8 role names are load-bearing for every
 * require_roles(...) check across the whole backend; the backend
 * itself blocks renaming/deleting them (SystemRoleProtectedException).
 *
 * Role names are proven immutable (RoleUpdateRequest has no `name`
 * field at all — verified), so checking against this fixed list is a
 * reliable, non-guessing way to gate the UI — the same reasoning
 * already used for utils/roleConfig.ts's role->panel mapping.
 *
 * IMPORTANT, verified directly in roles/service.py: system roles are
 * MORE locked than "delete-protected" — update_role() also rejects any
 * `status` change away from "active" for a system role (not just
 * deletion). Only `description` is genuinely editable for one.
 */
const SYSTEM_ROLE_NAMES = new Set([
  "Super Admin", "Admin", "Moderator", "Teacher",
  "Applicant", "Student", "Parent", "Guest",
]);

export function isSystemRole(roleName: string): boolean {
  return SYSTEM_ROLE_NAMES.has(roleName);
}
