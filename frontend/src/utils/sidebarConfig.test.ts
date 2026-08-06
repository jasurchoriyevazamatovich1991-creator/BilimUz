import { describe, expect, it } from "vitest";
import { sidebarForRole, APPLICANT_ITEMS, STUDENT_ITEMS, APPLICANT_STUDENT_ITEMS } from "./sidebarConfig";

describe("sidebarForRole", () => {
  it("returns different content for Applicant vs Student despite sharing a layout", () => {
    const applicantItems = sidebarForRole("Applicant");
    const studentItems = sidebarForRole("Student");
    expect(applicantItems).not.toEqual(studentItems);
    expect(applicantItems.some((i) => i.label === "DTM")).toBe(true);
    expect(studentItems.some((i) => i.label === "Mening fanlarim")).toBe(true);
  });

  it("returns an empty array for a role with no configured panel", () => {
    expect(sidebarForRole("Parent")).toEqual([]);
    expect(sidebarForRole("Guest")).toEqual([]);
  });

  it("Super Admin, Admin, and Moderator all get the same Admin sidebar", () => {
    expect(sidebarForRole("Super Admin")).toEqual(sidebarForRole("Admin"));
    expect(sidebarForRole("Moderator")).toEqual(sidebarForRole("Admin"));
  });
});

describe("Sprint 14 additions — Settings entries", () => {
  it("every role's sidebar includes a Sozlamalar entry", () => {
    for (const role of ["Super Admin", "Admin", "Moderator", "Teacher", "Applicant", "Student"]) {
      const items = sidebarForRole(role);
      expect(items.some((i) => i.label === "Sozlamalar")).toBe(true);
    }
  });

  it("Admin's Sozlamalar path is /admin/settings (pre-existing, Sprint 13)", () => {
    const settings = sidebarForRole("Admin").find((i) => i.label === "Sozlamalar");
    expect(settings?.path).toBe("/admin/settings");
  });

  it("Teacher's Sozlamalar path is /teacher/settings (new, Sprint 14)", () => {
    const settings = sidebarForRole("Teacher").find((i) => i.label === "Sozlamalar");
    expect(settings?.path).toBe("/teacher/settings");
  });
});

describe("Sprint 14 additions — Admin Profil entry", () => {
  it("Admin now has a Profil entry (Teacher/Student already had one in Sprint 13)", () => {
    const profil = sidebarForRole("Admin").find((i) => i.label === "Profil");
    expect(profil?.path).toBe("/admin/profile");
  });
});
describe("APPLICANT_STUDENT_ITEMS", () => {
  it("is the deduplicated union of both role's items", () => {
    const uniquePaths = new Set(APPLICANT_STUDENT_ITEMS.map((i) => i.path));
    expect(uniquePaths.size).toBe(APPLICANT_STUDENT_ITEMS.length);
  });

  it("contains every path from both APPLICANT_ITEMS and STUDENT_ITEMS", () => {
    const unionPaths = new Set(APPLICANT_STUDENT_ITEMS.map((i) => i.path));
    for (const item of [...APPLICANT_ITEMS, ...STUDENT_ITEMS]) {
      expect(unionPaths.has(item.path)).toBe(true);
    }
  });

  it("does not duplicate the shared Dashboard path", () => {
    const dashboardEntries = APPLICANT_STUDENT_ITEMS.filter((i) => i.path === "/student");
    expect(dashboardEntries).toHaveLength(1);
  });
});
