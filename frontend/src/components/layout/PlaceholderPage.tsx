/**
 * Every sidebar item this sprint that isn't the Dashboard renders this —
 * Sprint 13 scope is Foundation only (routing, layout, sidebar shell),
 * no business page functionality. Wiring each item to real functionality
 * is future-sprint work, tracked in the architecture doc's Section 12.
 */
interface PlaceholderPageProps {
  title: string;
}

export function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <div className="rounded-lg border border-dashed border-border p-12 text-center">
      <h2 className="text-lg font-medium text-foreground">{title}</h2>
      <p className="mt-2 text-sm text-foreground/60">Bu bo'lim keyingi sprintlarda ishlab chiqiladi.</p>
    </div>
  );
}
