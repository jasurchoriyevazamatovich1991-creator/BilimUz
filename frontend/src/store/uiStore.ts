/**
 * Sprint 89 — tiny transient UI store for the mobile nav drawer
 * (Sidebar.tsx/Header.tsx). Deliberately NOT persisted (unlike
 * authStore/themeStore) — whether the drawer is open has no meaning
 * across a page reload or a new tab, it should always start closed.
 * Its own store rather than folding into authStore: this is page-chrome
 * state, unrelated to the session data authStore holds.
 */
import { create } from "zustand";

interface UiState {
  isMobileNavOpen: boolean;
  openMobileNav: () => void;
  closeMobileNav: () => void;
  toggleMobileNav: () => void;
}

export const useUiStore = create<UiState>()((set) => ({
  isMobileNavOpen: false,
  openMobileNav: () => set({ isMobileNavOpen: true }),
  closeMobileNav: () => set({ isMobileNavOpen: false }),
  toggleMobileNav: () => set((s) => ({ isMobileNavOpen: !s.isMobileNavOpen })),
}));
