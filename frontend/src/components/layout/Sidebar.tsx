import { NavLink } from "react-router-dom";
import type { SidebarItem } from "@/utils/sidebarConfig";

interface SidebarProps {
  items: SidebarItem[];
}

export function Sidebar({ items }: SidebarProps) {
  return (
    <aside className="w-64 shrink-0 border-r border-border bg-background h-screen sticky top-0 overflow-y-auto">
      <div className="px-6 py-5 text-lg font-semibold text-primary">BilimUz</div>
      <nav className="px-3 space-y-1">
        {items.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path.split("/").length <= 2} // only the dashboard link (e.g. "/admin") is exact-match
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
  );
}
