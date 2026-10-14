/**
 * Sprint 89 — audit finding: AppRoutes.tsx had no catch-all route at
 * all, so any unknown URL (a typo, a stale bookmark, a removed link)
 * rendered a completely blank page — React Router simply renders
 * nothing when no <Route> matches. Mounted as a single top-level
 * `path="*"` in AppRoutes.tsx, outside every layout, so it works
 * whether or not the visitor is authenticated.
 *
 * The "go back" link is role-aware when possible (sends a logged-in
 * user to their own panel's home) and falls back to "/" otherwise —
 * reuses the existing resolvePanel/panelBasePath helpers already used
 * by ProtectedRoute.tsx, no new routing logic invented.
 */
import { Link } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { resolvePanel, panelBasePath } from "@/utils/roleConfig";

export function NotFoundPage() {
  const user = useAuthStore((s) => s.user);
  const homePath = user ? panelBasePath(resolvePanel(user.role)) : "/";

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
      <p className="text-sm font-semibold text-primary">404</p>
      <h1 className="mt-2 text-xl font-semibold text-foreground">Sahifa topilmadi</h1>
      <p className="mt-2 text-sm text-foreground/60">Siz qidirayotgan sahifa mavjud emas yoki ko'chirilgan.</p>
      <Link
        to={homePath}
        className="mt-6 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
      >
        Bosh sahifaga qaytish
      </Link>
    </div>
  );
}
