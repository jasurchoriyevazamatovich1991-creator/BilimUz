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
  active: "bg-green-100 text-green-700",
  inactive: "bg-gray-100 text-gray-600",
  banned: "bg-red-100 text-red-700",
  pending_verification: "bg-amber-100 text-amber-700",
};

interface StatusBadgeProps {
  status: string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const style = STATUS_STYLES[status] ?? "bg-gray-100 text-gray-600"; // unknown future status values still render, not blank
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${style}`}>{status}</span>;
}
