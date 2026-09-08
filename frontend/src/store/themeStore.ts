/**
 * New store — no dark-mode infrastructure existed before Sprint 24
 * (verified: tailwind.config.js had `darkMode: ["class"]` configured
 * but nothing ever applied the `.dark` class anywhere). Same Zustand +
 * persist pattern as authStore.ts, but deliberately its OWN store
 * (theme preference is unrelated to auth session data, shouldn't share
 * a slice or a persistence key with it).
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Theme = "light" | "dark";

interface ThemeState {
  theme: Theme;
  toggleTheme: () => void;
}

function applyThemeClass(theme: Theme) {
  const root = document.documentElement;
  if (theme === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: "light",
      toggleTheme: () => {
        const next: Theme = get().theme === "light" ? "dark" : "light";
        applyThemeClass(next);
        set({ theme: next });
      },
    }),
    {
      name: "bilimuz-theme",
      onRehydrateStorage: () => (state) => {
        // Applies the persisted preference to <html> on load — without
        // this, the class and the stored value could disagree after a
        // page refresh (store rehydrates, but nothing re-applies the class).
        if (state) applyThemeClass(state.theme);
      },
    },
  ),
);
