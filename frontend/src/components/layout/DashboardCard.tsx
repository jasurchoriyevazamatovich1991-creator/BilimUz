interface DashboardCardProps {
  title: string;
  isLoading?: boolean;
  value?: number | string;
}

/**
 * One composable card. Sprint 13 shipped this as empty/loading-state
 * only (no `value` prop existed); Sprint 14's approved scope
 * ("Dashboard backend integration") extends it to show real data —
 * this is the intended work for this sprint, not a rewrite of
 * something that was meant to stay frozen.
 */
export function DashboardCard({ title, isLoading = true, value }: DashboardCardProps) {
  return (
    <div className="rounded-lg border border-border p-5">
      <h3 className="text-sm font-medium text-foreground/70">{title}</h3>
      {isLoading ? (
        <div className="mt-3 h-8 w-20 animate-pulse rounded bg-primary/10" />
      ) : value !== undefined ? (
        <p className="mt-3 text-2xl font-semibold text-foreground">{value}</p>
      ) : (
        <p className="mt-3 text-sm text-foreground/50">Ma'lumot yo'q</p>
      )}
    </div>
  );
}
