/**
 * Minimal landing page — Sprint 13 scope is Foundation only, the full
 * marketing site (Hero, Tariflar, FAQ per ui_ux_blueprint.md §2) is
 * future-sprint work, not built here.
 */
export function HomePage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-24 text-center">
      <h1 className="text-3xl font-semibold text-foreground">BilimUz</h1>
      <p className="mt-4 text-foreground/60">O'zbekistonning AI-quvvatlangan ta'lim platformasi.</p>
    </div>
  );
}
