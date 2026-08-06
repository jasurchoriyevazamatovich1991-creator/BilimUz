interface UnavailableStateProps {
  title: string;
}

/**
 * Distinct from ErrorState (a FAILED fetch) — this is for widgets whose
 * data literally has no backing endpoint yet (e.g. Super Admin's
 * "Natijalar" — no admin-wide GET /results list exists, only /results/me,
 * verified before writing this component). Never silently faked or
 * omitted — shown honestly as its own state, per Architecture Freeze.
 */
export function UnavailableState({ title }: UnavailableStateProps) {
  return (
    <div className="rounded-lg border border-dashed border-border p-5">
      <h3 className="text-sm font-medium text-foreground/70">{title}</h3>
      <p className="mt-3 text-sm text-foreground/40">Hozircha mavjud emas</p>
    </div>
  );
}
