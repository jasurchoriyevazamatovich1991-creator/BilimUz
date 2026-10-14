import { useEffect } from "react";
import { NavLink } from "react-router-dom";
import type { SidebarItem } from "@/utils/sidebarConfig";
import { useUiStore } from "@/store/uiStore";
import { cn } from "@/lib/utils";

interface SidebarProps {
  items: SidebarItem[];
}

/**
 * Sprint 89 fix — audit finding: this sidebar was a fixed `w-64
 * shrink-0` column with zero responsive handling, shared by every
 * authenticated layout (Student/Admin/Teacher). On a narrow viewport
 * that meant permanent horizontal overflow (or the main content
 * squeezed unusably thin) and no way to reach navigation without
 * zooming out — confirmed by inspecting every layout file, all three
 * render this component unconditionally inside a `flex` row with no
 * breakpoint logic anywhere above it.
 *
 * Fixed as a standard responsive drawer, reusing Tailwind's existing
 * `lg` breakpoint (already the project's convention for the dashboard
 * grids — see e.g. StudentDashboardPage.tsx's `lg:grid-cols-4`):
 * - Below `lg`: `fixed` (removed from flow — the content column no
 *   longer reserves its width) and translated off-screen by default;
 *   `useUiStore`'s `isMobileNavOpen` slides it in as an overlay with a
 *   backdrop, closed again by the backdrop, Escape, or by following a
 *   link (so navigating doesn't leave the drawer open over the next page).
 * - At `lg` and above: back to the original always-visible `sticky`
 *   column — byte-for-byte the same desktop appearance as before.
 */
export function Sidebar({ items }: SidebarProps) {
  const isOpen = useUiStore((s) => s.isMobileNavOpen);
  const close = useUiStore((s) => s.closeMobileNav);

  useEffect(() => {
    if (!isOpen) return;
    function handleEscape(e: KeyboardEvent) {
      if (e.key === "Escape") close();
    }
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, close]);

  return (
    <>
      {isOpen ? (
        <div
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          aria-hidden="true"
          onClick={close}
        />
      ) : null}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 w-64 shrink-0 overflow-y-auto border-r border-border bg-background transition-transform duration-200 ease-in-out",
          "lg:sticky lg:top-0 lg:z-auto lg:h-screen lg:translate-x-0",
          isOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="px-6 py-5 text-lg font-semibold text-primary">BilimUz</div>
        <nav className="px-3 space-y-1">
          {items.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path.split("/").length <= 2} // only the dashboard link (e.g. "/admin") is exact-match
              onClick={close} // following a link should never leave the mobile drawer open over the next page
              className={({ isActive }) =>
                `block rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive ? "bg-primary text-primary-foreground" : "text-foreground hover:bg-primary/10"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
    </>
  );
}
