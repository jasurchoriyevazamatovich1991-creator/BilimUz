import { Link, Outlet } from "react-router-dom";

export function PublicLayout() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="flex items-center justify-between border-b border-border px-6 py-4">
        <Link to="/" className="text-lg font-semibold text-primary">
          BilimUz
        </Link>
        <nav className="flex items-center gap-4 text-sm">
          <Link to="/login" className="text-foreground/70 hover:text-primary">
            Kirish
          </Link>
          <Link to="/register" className="rounded-md bg-primary px-4 py-2 text-primary-foreground hover:opacity-90">
            Ro'yxatdan o'tish
          </Link>
        </nav>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
