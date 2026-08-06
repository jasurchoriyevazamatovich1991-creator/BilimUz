/**
 * Route-level RBAC guard — mirrors the backend's require_roles()
 * dependency: declared once at the layout boundary, not scattered
 * through every page. This is UI convenience, NOT security — the
 * backend's own require_roles() remains the actual enforcement (never
 * trust the client), exactly as stated in the approved architecture
 * doc's Section 10.
 */
import { Navigate, Outlet } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { resolvePanel, panelBasePath, type PanelKey } from "@/utils/roleConfig";

interface ProtectedRouteProps {
  allowedPanel: PanelKey;
}

export function ProtectedRoute({ allowedPanel }: ProtectedRouteProps) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const user = useAuthStore((s) => s.user);

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  const actualPanel = resolvePanel(user.role);
  if (actualPanel !== allowedPanel) {
    // Never a blank screen — redirect to the panel this user actually
    // belongs to, per the approved architecture doc's Section 10.
    return <Navigate to={panelBasePath(actualPanel)} replace />;
  }

  return <Outlet />;
}
