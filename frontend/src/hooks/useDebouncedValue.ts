/**
 * Minimal debounce hook — no external library (approved decision).
 * Returns `value` only after it hasn't changed for `delayMs`, so a
 * search input can update local state instantly (responsive typing)
 * while the actual API call fires only once typing pauses.
 */
import { useEffect, useState } from "react";

export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
