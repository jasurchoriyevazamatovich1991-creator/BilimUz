/**
 * Role -> panel mapping. The 8 role names below are read directly from
 * the real seed data (database/schema/schema_v2.sql, the `INSERT INTO
 * roles` statement) — not invented, not a subset. Grouping into panels
 * follows docs/UI-UX/ui_ux_blueprint.md's own navigation map exactly:
 *   Super Admin / Admin / Moderator → Admin Panel (Moderator "cheklangan"
 *     per the blueprint — the restriction itself is a future RBAC-UI
 *     concern, not this sprint's scope; Moderator gets the Admin shell)
 *   Teacher                         → Teacher Panel
 *   Applicant / Student              → Student Panel
 *   Parent                            → "Parent Panel (v2)" per the
 *     blueprint — does not exist yet. Mapped to `unsupported`, NOT
 *     silently folded into another panel (that would show a Parent
 *     content they don't have).
 *   Guest                              → not a real assigned role for an
 *     authenticated session in practice; also `unsupported` defensively.
 */
export type PanelKey = "admin" | "teacher" | "student" | "unsupported";

const ROLE_TO_PANEL: Record<string, PanelKey> = {
  "Super Admin": "admin",
  Admin: "admin",
  Moderator: "admin",
  Teacher: "teacher",
  Applicant: "student",
  Student: "student",
  Parent: "unsupported",
  Guest: "unsupported",
};

export function resolvePanel(roleName: string): PanelKey {
  return ROLE_TO_PANEL[roleName] ?? "unsupported";
}

export function panelBasePath(panel: PanelKey): string {
  switch (panel) {
    case "admin":
      return "/admin";
    case "teacher":
      return "/teacher";
    case "student":
      return "/student";
    case "unsupported":
      return "/unsupported";
  }
}
