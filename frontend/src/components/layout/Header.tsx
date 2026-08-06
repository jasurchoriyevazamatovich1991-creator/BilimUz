import { useAuthStore } from "@/store/authStore";
import { useLogout } from "@/hooks/useAuth";

export function Header() {
  const user = useAuthStore((s) => s.user);
  const { mutate: logout, isPending } = useLogout();

  return (
    <header className="flex items-center justify-between border-b border-border bg-background px-6 py-4">
      <div className="text-sm text-foreground/70">
        {user ? `${user.first_name} ${user.last_name}` : ""}
        {user?.role ? <span className="ml-2 rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">{user.role}</span> : null}
      </div>
      <button
        type="button"
        onClick={() => logout()}
        disabled={isPending}
        className="rounded-md px-3 py-1.5 text-sm font-medium text-foreground/70 hover:bg-primary/10 disabled:opacity-50"
      >
        Chiqish
      </button>
    </header>
  );
}
