import { Outlet } from "react-router-dom";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { useAuthStore } from "@/store/authStore";
import { sidebarForRole } from "@/utils/sidebarConfig";

/**
 * Used by BOTH the Student and Applicant roles (same layout shell per
 * ui_ux_blueprint.md's navigation map) — sidebarForRole() supplies the
 * role-specific item list (they differ, see sidebarConfig.ts), the
 * shell itself does not.
 *
 * NOTE: the test-taking screen (ui_ux_blueprint.md §4.3) explicitly does
 * NOT use this layout — it needs a dedicated full-screen shell with no
 * sidebar/header chrome, out of this sprint's scope (see architecture
 * doc Section 7's own flag). Not built here.
 */
export function StudentLayout() {
  const user = useAuthStore((s) => s.user);
  const items = sidebarForRole(user?.role ?? "");

  return (
    <div className="flex min-h-screen">
      <Sidebar items={items} />
      <div className="flex-1 flex flex-col">
        <Header />
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
