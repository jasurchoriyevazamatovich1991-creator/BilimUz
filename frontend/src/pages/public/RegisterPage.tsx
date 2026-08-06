import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useRegister } from "@/hooks/useAuth";
import { ApiError } from "@/api/client";

export function RegisterPage() {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const { mutate: register, isPending, error } = useRegister();
  const navigate = useNavigate();

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    register(
      { first_name: firstName, last_name: lastName, phone, password },
      {
        onSuccess: (result) => {
          // The backend does not send a real SMS yet (see api/auth.ts's
          // RegisterResponse docstring) — `debug_code` is passed through
          // to the Verify page via navigation state exactly as the
          // backend returned it. No mock/fake delivery is simulated here.
          navigate("/verify", { state: { userId: result.user_id, debugCode: result.debug_code } });
        },
      },
    );
  }

  const errorMessage = error instanceof ApiError ? error.message : null;

  return (
    <div className="mx-auto flex max-w-md flex-col justify-center px-6 py-16">
      <h1 className="mb-6 text-2xl font-semibold text-foreground">Ro'yxatdan o'tish</h1>

      {errorMessage ? (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {errorMessage}
        </div>
      ) : null}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="firstName" className="mb-1 block text-sm font-medium text-foreground">
              Ism
            </label>
            <input
              id="firstName"
              required
              minLength={2}
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              className="w-full rounded-md border border-border px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label htmlFor="lastName" className="mb-1 block text-sm font-medium text-foreground">
              Familiya
            </label>
            <input
              id="lastName"
              required
              minLength={2}
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              className="w-full rounded-md border border-border px-3 py-2 text-sm"
            />
          </div>
        </div>
        <div>
          <label htmlFor="phone" className="mb-1 block text-sm font-medium text-foreground">
            Telefon raqam
          </label>
          <input
            id="phone"
            required
            placeholder="+998901234567"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
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
            minLength={12}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border border-border px-3 py-2 text-sm"
          />
          <p className="mt-1 text-xs text-foreground/50">Kamida 12 belgi</p>
        </div>
        <button
          type="submit"
          disabled={isPending}
          className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
        >
          {isPending ? "Yuborilmoqda..." : "Ro'yxatdan o'tish"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-foreground/60">
        Akkountingiz bormi?{" "}
        <Link to="/login" className="text-primary hover:underline">
          Kirish
        </Link>
      </p>
    </div>
  );
}
