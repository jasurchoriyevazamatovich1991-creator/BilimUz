import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { useLogout } from "@/hooks/useAuth";
import { resolvePanel, panelBasePath } from "@/utils/roleConfig";

/**
 * Sprint 14: replaces Sprint 13's single flat "Chiqish" button with a
 * real dropdown (approved decision). Profile links to the existing
 * placeholder-page mechanism (AppRoutes.tsx's placeholderRoutesFor, not
 * touched) — shows "Bu bo'lim keyingi sprintlarda ishlab chiqiladi."
 * which serves as the approved "Coming Soon" messaging, reusing the
 * already-existing PlaceholderPage component rather than building a
 * new one for the same purpose.
 */
export function Header() {
  const user = useAuthStore((s) => s.user);
  const { mutate: logout, isPending } = useLogout();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    function handleEscape(e: KeyboardEvent) {
      if (e.key === "Escape") setIsOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  if (!user) return null;

  const basePath = panelBasePath(resolvePanel(user.role));
  const profilePath = `${basePath}/profile`;
  const settingsPath = `${basePath}/settings`;

  return (
    <header className="flex items-center justify-between border-b border-border bg-background px-6 py-4">
      <div />
      <div ref={menuRef} className="relative">
        <button
          type="button"
          onClick={() => setIsOpen((v) => !v)}
          aria-expanded={isOpen}
          aria-haspopup="menu"
          className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-foreground/70 hover:bg-primary/10"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
            {user.first_name[0]}
            {user.last_name[0]}
          </span>
          <span>{user.first_name} {user.last_name}</span>
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">{user.role}</span>
        </button>

        {isOpen ? (
          <div
            role="menu"
            className="absolute right-0 top-full mt-1 w-48 rounded-md border border-border bg-background py-1 shadow-md"
          >
            <Link
              to={profilePath}
              role="menuitem"
              onClick={() => setIsOpen(false)}
              className="block px-4 py-2 text-sm text-foreground hover:bg-primary/10"
            >
              Profil
            </Link>
            <Link
              to={settingsPath}
              role="menuitem"
              onClick={() => setIsOpen(false)}
              className="block px-4 py-2 text-sm text-foreground hover:bg-primary/10"
            >
              Sozlamalar
            </Link>
            <button
              type="button"
              role="menuitem"
              onClick={() => logout()}
              disabled={isPending}
              className="block w-full px-4 py-2 text-left text-sm text-foreground hover:bg-primary/10 disabled:opacity-50"
            >
              Chiqish
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
}
