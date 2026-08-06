/**
 * Sidebar navigation items PER ROLE — copied directly from the
 * already-authored docs/UI-UX/panel_modules.md, not redesigned. Keyed
 * by role name (not panel) deliberately: Applicant and Student share
 * the same LAYOUT ("Student Panel" per ui_ux_blueprint.md's navigation
 * map) but have DIFFERENT sidebar content in panel_modules.md — keying
 * by panel alone would have silently collapsed that real distinction.
 *
 * Every `path` this sprint routes to a placeholder page (Sprint 13
 * scope: Foundation only, no business pages) — wiring each to real
 * functionality is future-sprint work.
 */
export interface SidebarItem {
  label: string;
  path: string;
}

export const ADMIN_ITEMS: SidebarItem[] = [
  { label: "Dashboard", path: "/admin" },
  { label: "Foydalanuvchilar", path: "/admin/users" },
  { label: "Rollar", path: "/admin/roles" },
  { label: "Ruxsatlar", path: "/admin/permissions" },
  { label: "Fanlar", path: "/admin/subjects" },
  { label: "Sinflar", path: "/admin/grades" },
  { label: "Mavzular", path: "/admin/topics" },
  { label: "Darslar", path: "/admin/lessons" },
  { label: "Testlar", path: "/admin/tests" },
  { label: "Savollar", path: "/admin/questions" },
  { label: "Natijalar", path: "/admin/results" },
  { label: "Sertifikatlar", path: "/admin/certificates" },
  { label: "Analitika", path: "/admin/analytics" },
  { label: "To'lovlar", path: "/admin/payments" },
  { label: "Bildirishnomalar", path: "/admin/notifications" },
  { label: "AI", path: "/admin/ai" },
  { label: "Sozlamalar", path: "/admin/settings" },
];

export const TEACHER_ITEMS: SidebarItem[] = [
  { label: "Dashboard", path: "/teacher" },
  { label: "Attestatsiya", path: "/teacher/attestation" },
  { label: "Milliy Sertifikat", path: "/teacher/national-certificate" },
  { label: "Testlar", path: "/teacher/tests" },
  { label: "Natijalar", path: "/teacher/results" },
  { label: "Statistika", path: "/teacher/statistics" },
  { label: "Profil", path: "/teacher/profile" },
];

// Applicant (Abituriyent) — NOT the same content as Student, per
// panel_modules.md, despite sharing the same layout shell.
export const APPLICANT_ITEMS: SidebarItem[] = [
  { label: "Dashboard", path: "/student" },
  { label: "DTM", path: "/student/dtm" },
  { label: "Blok Test", path: "/student/blok-test" },
  { label: "Mavzular", path: "/student/topics" },
  { label: "Natijalar", path: "/student/results" },
  { label: "Reyting", path: "/student/ranking" },
  { label: "AI Ustoz", path: "/student/ai" },
  { label: "Profil", path: "/student/profile" },
];

export const STUDENT_ITEMS: SidebarItem[] = [
  { label: "Dashboard", path: "/student" },
  { label: "Mening fanlarim", path: "/student/subjects" },
  { label: "Darslar", path: "/student/lessons" },
  { label: "Testlar", path: "/student/tests" },
  { label: "Natijalar", path: "/student/results" },
  { label: "Yutuqlar", path: "/student/achievements" },
  { label: "Profil", path: "/student/profile" },
];

/**
 * The Student PANEL (layout) serves two roles — Applicant and Student —
 * with different sidebar content each (see sidebarForRole()). Route
 * definitions (AppRoutes.tsx) need the UNION of both role's paths, so
 * whichever role is actually logged in, every path their own sidebar
 * links to resolves to a real route. Deduplicated by path (both
 * variants share "Dashboard" -> "/student").
 */
export const APPLICANT_STUDENT_ITEMS: SidebarItem[] = Array.from(
  new Map([...APPLICANT_ITEMS, ...STUDENT_ITEMS].map((item) => [item.path, item])).values(),
);

const SIDEBAR_BY_ROLE: Record<string, SidebarItem[]> = {
  "Super Admin": ADMIN_ITEMS,
  Admin: ADMIN_ITEMS,
  Moderator: ADMIN_ITEMS,
  Teacher: TEACHER_ITEMS,
  Applicant: APPLICANT_ITEMS,
  Student: STUDENT_ITEMS,
};

export function sidebarForRole(roleName: string): SidebarItem[] {
  return SIDEBAR_BY_ROLE[roleName] ?? [];
}
