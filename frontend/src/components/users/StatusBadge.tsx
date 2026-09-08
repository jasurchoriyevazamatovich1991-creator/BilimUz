/**
 * Display-only. Per approved decision 5: renders whatever status the
 * backend returns — including "banned", which exists as a valid User
 * model status (verified: users/models.py's UserStatus enum) even
 * though no endpoint can currently SET it (users/constants.py's
 * ADMIN_SETTABLE_STATUSES only allows active/inactive — see
 * docs/Sprint15_..._Architecture.md's Critical Finding). No ban/unban
 * action anywhere in this component — status is never hidden or
 * reinterpreted, just colored for readability.
 */
const STATUS_STYLES: Record<string, string> = {
  active: "bg-success/15 text-success",
  inactive: "bg-muted text-muted-foreground",
  banned: "bg-destructive/15 text-destructive",
  pending_verification: "bg-warning/15 text-warning",
};

interface StatusBadgeProps {
  status: string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const style = STATUS_STYLES[status] ?? "bg-muted text-muted-foreground"; // unknown future status values still render, not blank
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${style}`}>{status}</span>;
}
