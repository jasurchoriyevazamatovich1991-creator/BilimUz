import { describe, expect, it, beforeEach } from "vitest";
import { useThemeStore } from "./themeStore";

describe("themeStore", () => {
  beforeEach(() => {
    useThemeStore.setState({ theme: "light" });
    document.documentElement.classList.remove("dark");
  });

  it("defaults to light", () => {
    expect(useThemeStore.getState().theme).toBe("light");
  });

  it("toggleTheme switches light -> dark", () => {
    useThemeStore.getState().toggleTheme();
    expect(useThemeStore.getState().theme).toBe("dark");
  });

  it("toggleTheme switches dark -> light on a second call", () => {
    useThemeStore.getState().toggleTheme();
    useThemeStore.getState().toggleTheme();
    expect(useThemeStore.getState().theme).toBe("light");
  });

  it("applies the .dark class to <html> when toggled to dark", () => {
    useThemeStore.getState().toggleTheme();
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("removes the .dark class when toggled back to light", () => {
    useThemeStore.getState().toggleTheme();
    useThemeStore.getState().toggleTheme();
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});
