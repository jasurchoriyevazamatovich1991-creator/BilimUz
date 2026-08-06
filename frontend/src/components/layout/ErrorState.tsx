interface ErrorStateProps {
  title: string;
}

/**
 * The inline-error counterpart to DashboardCard (same file, same
 * visual family) — approved decision: widget errors show inline here
 * AND trigger a global toast (see useDashboardStats.ts's onError),
 * not one or the other.
 */
export function ErrorState({ title }: ErrorStateProps) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-5">
      <h3 className="text-sm font-medium text-red-700/70">{title}</h3>
      <p className="mt-3 text-sm text-red-700">Yuklab bo'lmadi</p>
    </div>
  );
}
