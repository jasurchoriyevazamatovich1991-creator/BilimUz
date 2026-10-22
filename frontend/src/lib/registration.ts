/**
 * Task 10.1 — public self-registration is off unless the deployment
 * explicitly enables it (VITE_PUBLIC_REGISTRATION_ENABLED=true, matching the
 * backend's PUBLIC_REGISTRATION_ENABLED). Accounts are created by an
 * administrator (Admin panel → Foydalanuvchilar → Foydalanuvchi qo'shish).
 */
export function isPublicRegistrationEnabled(): boolean {
  return import.meta.env.VITE_PUBLIC_REGISTRATION_ENABLED === "true";
}

/** Roles an administrator may give a new account (mirrors backend
 * users/constants.CREATABLE_ROLES_BY_ACTOR; the backend re-checks). */
export function creatableRoles(actorRole: string | null | undefined): string[] {
  if (actorRole === "Super Admin") return ["Student", "Teacher", "Admin"];
  if (actorRole === "Admin") return ["Student", "Teacher"];
  return [];
}
