import { Outlet } from "react-router-dom";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { useAuthStore } from "@/store/authStore";
import { sidebarForRole } from "@/utils/sidebarConfig";

export function AdminLayout() {
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
