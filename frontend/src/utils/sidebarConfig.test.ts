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
