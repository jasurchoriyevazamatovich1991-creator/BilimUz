/**
 * Display-only, same pattern as components/users/StatusBadge.tsx but a
 * distinct component (not a StatusBadge extension) because the status
 * domain is different: active/scheduled/expired/revoked, not
 * active/inactive/banned/pending_verification. Always renders the
 * server-computed `effective_status` — never recomputed here (spec §6
 * — "avoid relying on frontend-only expiration checks").
 */
const STATUS_STYLES: Record<string, string> = {
  active: "bg-success/15 text-success",
  scheduled: "bg-primary/15 text-primary",
  expired: "bg-muted text-muted-foreground",
  revoked: "bg-destructive/15 text-destructive",
};

const STATUS_LABELS: Record<string, string> = {
  active: "Faol",
  scheduled: "Rejalashtirilgan",
  expired: "Muddati tugagan",
  revoked: "Bekor qilingan",
};

interface EntitlementStatusBadgeProps {
  status: string;
}

export function EntitlementStatusBadge({ status }: EntitlementStatusBadgeProps) {
  const style = STATUS_STYLES[status] ?? "bg-muted text-muted-foreground";
  const label = STATUS_LABELS[status] ?? status;
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${style}`}>{label}</span>;
}
