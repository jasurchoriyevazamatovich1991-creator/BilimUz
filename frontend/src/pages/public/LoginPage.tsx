import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useLogin } from "@/hooks/useAuth";
import { ApiError } from "@/api/client";

export function LoginPage() {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const { mutate: login, isPending, error } = useLogin();

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    login({ identifier, password });
  }

  const errorMessage = error instanceof ApiError ? error.message : null;

  return (
    <div className="mx-auto flex max-w-md flex-col justify-center px-6 py-16">
      <h1 className="mb-6 text-2xl font-semibold text-foreground">Tizimga kirish</h1>

      {errorMessage ? (
        // Per ui_ux_blueprint.md §3: form errors show as a banner ABOVE
        // the form, never a toast — the error must stay visually tied
        // to the form that produced it.
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {errorMessage}
        </div>
      ) : null}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="identifier" className="mb-1 block text-sm font-medium text-foreground">
            Telefon yoki email
          </label>
          <input
            id="identifier"
            type="text"
            required
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            className="w-full rounded-md border border-border px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label htmlFor="password" className="mb-1 block text-sm font-medium text-foreground">
            Parol
          </label>
          <input
            id="password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border border-border px-3 py-2 text-sm"
          />
        </div>
        <button
          type="submit"
          disabled={isPending}
          className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
        >
          {isPending ? "Kirilmoqda..." : "Kirish"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-foreground/60">
        Akkountingiz yo'qmi?{" "}
        <Link to="/register" className="text-primary hover:underline">
          Ro'yxatdan o'ting
        </Link>
      </p>
    </div>
  );
}
