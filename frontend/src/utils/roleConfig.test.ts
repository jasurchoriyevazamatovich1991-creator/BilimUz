import { describe, expect, it } from "vitest";
import { resolvePanel, panelBasePath } from "./roleConfig";

describe("resolvePanel", () => {
  it.each([
    ["Super Admin", "admin"],
    ["Admin", "admin"],
    ["Moderator", "admin"],
    ["Teacher", "teacher"],
    ["Applicant", "student"],
    ["Student", "student"],
  ])("maps %s -> %s", (role, expected) => {
    expect(resolvePanel(role)).toBe(expected);
  });

  it("maps Parent to unsupported, not silently into another panel", () => {
    expect(resolvePanel("Parent")).toBe("unsupported");
  });

  it("maps Guest to unsupported", () => {
    expect(resolvePanel("Guest")).toBe("unsupported");
  });

  it("defaults unknown role names to unsupported rather than throwing", () => {
    expect(resolvePanel("SomeFutureRole")).toBe("unsupported");
  });
});

describe("panelBasePath", () => {
  it("returns the correct base path for each panel", () => {
    expect(panelBasePath("admin")).toBe("/admin");
    expect(panelBasePath("teacher")).toBe("/teacher");
    expect(panelBasePath("student")).toBe("/student");
    expect(panelBasePath("unsupported")).toBe("/unsupported");
  });
});
