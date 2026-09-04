import { describe, expect, it } from "vitest";
import { isSystemRole } from "./systemRoles";

describe("isSystemRole", () => {
  it.each(["Super Admin", "Admin", "Moderator", "Teacher", "Applicant", "Student", "Parent", "Guest"])(
    "recognizes '%s' as a system role (matches backend SYSTEM_ROLE_NAMES exactly)",
    (name) => {
      expect(isSystemRole(name)).toBe(true);
    },
  );

  it("returns false for a custom role name", () => {
    expect(isSystemRole("Content Reviewer")).toBe(false);
  });

  it("is case-sensitive (matches the backend's exact string comparison)", () => {
    expect(isSystemRole("teacher")).toBe(false);
    expect(isSystemRole("TEACHER")).toBe(false);
  });
});
