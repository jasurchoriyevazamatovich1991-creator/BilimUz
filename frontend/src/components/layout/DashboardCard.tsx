interface DashboardCardProps {
  title: string;
  isLoading?: boolean;
}

/**
 * One composable card, per the approved architecture doc's Section 9 —
 * empty/loading state only this sprint, no real data-driven widgets
 * (those need working list/detail pages first, out of scope).
 */
export function DashboardCard({ title, isLoading = true }: DashboardCardProps) {
  return (
    <div className="rounded-lg border border-border p-5">
      <h3 className="text-sm font-medium text-foreground/70">{title}</h3>
      {isLoading ? (
        <div className="mt-3 h-8 w-20 animate-pulse rounded bg-primary/10" />
      ) : (
        <p className="mt-3 text-sm text-foreground/50">Ma'lumot yo'q</p>
      )}
    </div>
  );
}
