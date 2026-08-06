/**
 * Shown to roles with no panel built yet — Parent ("Parent Panel (v2)"
 * per ui_ux_blueprint.md, doesn't exist) and Guest (not a real
 * assigned session role in practice). Deliberately its own honest page,
 * not silently redirected into another role's real panel.
 */
export function UnsupportedRolePage() {
  return (
    <div className="mx-auto max-w-md px-6 py-24 text-center">
      <h1 className="text-xl font-semibold text-foreground">Panel hali tayyor emas</h1>
      <p className="mt-2 text-sm text-foreground/60">Sizning rolingiz uchun panel keyingi versiyalarda qo'shiladi.</p>
    </div>
  );
}
