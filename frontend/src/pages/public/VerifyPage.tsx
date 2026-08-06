import { useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useVerify } from "@/hooks/useAuth";
import { ApiError } from "@/api/client";

interface VerifyLocationState {
  userId: string;
  debugCode: string;
}

const CODE_LENGTH = 6;

export function VerifyPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as VerifyLocationState | null;

  const [digits, setDigits] = useState<string[]>(Array(CODE_LENGTH).fill(""));
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);
  const { mutate: verify, isPending, error } = useVerify();

  if (!state?.userId) {
    // Reached directly (e.g. page refresh) without coming from
    // Register — there's no user_id to verify, send them back rather
    // than show a broken form.
    navigate("/register", { replace: true });
    return null;
  }

  function handleDigitChange(index: number, value: string) {
    if (!/^\d?$/.test(value)) return; // one digit only, per ui_ux_blueprint.md's "6 ta katak"
    const next = [...digits];
    next[index] = value;
    setDigits(next);

    if (value && index < CODE_LENGTH - 1) {
      inputRefs.current[index + 1]?.focus(); // auto-focus next box, per the documented UX
    }

    const code = next.join("");
    if (code.length === CODE_LENGTH) {
      verify(
        { user_id: state.userId, code },
        {
          // POST /auth/verify returns UserPublic, NOT tokens (verified
          // against the real backend router.py) — there is no
          // auto-login here. The user must log in separately, per the
          // documented flow (ui_ux_blueprint.md §3: Verify -> Login is
          // implicit, tokens are only ever issued by POST /auth/login).
          onSuccess: () => navigate("/login", { replace: true, state: { justVerified: true } }),
        },
      );
    }
  }

  function handleKeyDown(index: number, e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Backspace" && !digits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  }

  const errorMessage = error instanceof ApiError ? error.message : null;

  return (
    <div className="mx-auto flex max-w-md flex-col justify-center px-6 py-16 text-center">
      <h1 className="mb-2 text-2xl font-semibold text-foreground">Tasdiqlash</h1>
      <p className="mb-6 text-sm text-foreground/60">Kodni kiriting</p>

      {/* Backend has no real SMS delivery yet (see api/auth.ts) — the
          debug_code is shown here as-is, exactly as the backend
          returned it. Not a fake/mocked delivery mechanism. */}
      <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        Vaqtinchalik kod (SMS hali ulanmagan): <strong>{state.debugCode}</strong>
      </div>

      {errorMessage ? (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {errorMessage}
        </div>
      ) : null}

      <div className="mb-6 flex justify-center gap-2">
        {digits.map((digit, i) => (
          <input
            key={i}
            ref={(el) => {
              inputRefs.current[i] = el;
            }}
            type="text"
            inputMode="numeric"
            maxLength={1}
            value={digit}
            disabled={isPending}
            onChange={(e) => handleDigitChange(i, e.target.value)}
            onKeyDown={(e) => handleKeyDown(i, e)}
            className="h-12 w-12 rounded-md border border-border text-center text-lg font-medium"
          />
        ))}
      </div>

      {isPending ? <p className="text-sm text-foreground/60">Tekshirilmoqda...</p> : null}
    </div>
  );
}
