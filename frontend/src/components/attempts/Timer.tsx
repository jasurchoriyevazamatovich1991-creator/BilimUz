/**
 * Approved decision 2: purely visual countdown, computed fresh from
 * `expiresAt` (backend-supplied) on every render/interval tick — NEVER
 * reads or writes localStorage. On refresh, this component simply
 * re-mounts with a fresh `expiresAt` (from the re-fetched attempt, see
 * hooks/useAttempt.ts's useAttempt()) and recomputes the remaining time
 * correctly — no separate persistence needed, no drift.
 *
 * Calls `onExpire` at most ONCE (a ref guard, not state, so it can't
 * double-fire across renders) when the countdown reaches zero. The
 * caller (AttemptPage.tsx) is responsible for the actual submit call
 * and for not racing it against a manual submit — this component only
 * signals "time is up", it never calls the API itself.
 */
import { useEffect, useRef, useState } from "react";

interface TimerProps {
  expiresAt: string;
  onExpire: () => void;
}

function formatRemaining(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function Timer({ expiresAt, onExpire }: TimerProps) {
  const expiresAtMs = new Date(expiresAt).getTime();
  const [remainingMs, setRemainingMs] = useState(() => expiresAtMs - Date.now());
  const hasExpiredRef = useRef(false);

  useEffect(() => {
    hasExpiredRef.current = false; // reset if a new expiresAt ever arrives (e.g. a different attempt)

    const interval = setInterval(() => {
      const remaining = expiresAtMs - Date.now();
      setRemainingMs(remaining);
      if (remaining <= 0 && !hasExpiredRef.current) {
        hasExpiredRef.current = true;
        clearInterval(interval);
        onExpire();
      }
    }, 1000);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expiresAtMs]);

  const isLow = remainingMs <= 5 * 60 * 1000; // matches ui_ux_blueprint.md's documented "5 daqiqa qolganda qizarish" behavior

  return (
    <span className={`font-mono text-sm font-medium ${isLow ? "text-red-600" : "text-foreground/70"}`}>
      {formatRemaining(remainingMs)}
    </span>
  );
}
