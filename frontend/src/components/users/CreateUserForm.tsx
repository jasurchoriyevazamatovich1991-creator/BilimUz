/**
 * Task 10.1 — administrator-managed account creation (public
 * self-registration is disabled). The created account is active at once;
 * the administrator hands the login (phone/email) and password to the user.
 * Role options follow the actor's own role; the backend re-checks and
 * rejects anything else with 403.
 */
import { useId, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCreateUser } from "@/hooks/useUsers";
import { useAuthStore } from "@/store/authStore";
import { creatableRoles } from "@/lib/registration";

const ROLE_LABELS: Record<string, string> = { Student: "O'quvchi", Teacher: "O'qituvchi", Admin: "Administrator" };

export function CreateUserForm({ onDone }: { onDone: () => void }) {
  const id = useId();
  const actorRole = useAuthStore((s) => s.user?.role);
  const roles = creatableRoles(actorRole);
  const create = useCreateUser();
  const [values, setValues] = useState({ first_name: "", last_name: "", phone: "", email: "", password: "", role: roles[0] ?? "Student" });
  const set = (k: keyof typeof values) => (e: { target: { value: string } }) => setValues((v) => ({ ...v, [k]: e.target.value }));

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    create.mutate(
      { ...values, email: values.email.trim() || undefined, phone: values.phone.trim() },
      { onSuccess: onDone },
    );
  }

  if (roles.length === 0) return null;

  return (
    <form onSubmit={handleSubmit} className="mb-6 grid grid-cols-1 gap-3 rounded-md border border-border p-4 sm:grid-cols-2" data-testid="create-user-form">
      {([
        ["first_name", "Ism", "text"], ["last_name", "Familiya", "text"],
        ["phone", "Telefon (+998…)", "tel"], ["email", "Email (ixtiyoriy)", "email"],
      ] as const).map(([key, label, type]) => (
        <div key={key}>
          <label htmlFor={`${id}-${key}`} className="mb-1 block text-xs font-medium text-foreground/70">{label}</label>
          <Input id={`${id}-${key}`} type={type} value={values[key]} onChange={set(key)} required={key !== "email"} />
        </div>
      ))}
      <div>
        <label htmlFor={`${id}-password`} className="mb-1 block text-xs font-medium text-foreground/70">Boshlang'ich parol (kamida 12 belgi)</label>
        <Input id={`${id}-password`} type="password" autoComplete="new-password" value={values.password} onChange={set("password")} required minLength={12} />
      </div>
      <div>
        <label htmlFor={`${id}-role`} className="mb-1 block text-xs font-medium text-foreground/70">Rol</label>
        <select id={`${id}-role`} value={values.role} onChange={set("role")} className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm">
          {roles.map((r) => <option key={r} value={r}>{ROLE_LABELS[r] ?? r}</option>)}
        </select>
      </div>
      <p className="text-xs text-foreground/60 sm:col-span-2">
        Akkaunt darhol faol bo'ladi. Login (telefon yoki email) va parolni foydalanuvchiga xavfsiz yo'l bilan bering.
      </p>
      <div className="flex gap-2 sm:col-span-2">
        <Button type="submit" disabled={create.isPending}>{create.isPending ? "..." : "Yaratish"}</Button>
        <Button type="button" variant="outline" onClick={onDone}>Bekor qilish</Button>
      </div>
    </form>
  );
}
