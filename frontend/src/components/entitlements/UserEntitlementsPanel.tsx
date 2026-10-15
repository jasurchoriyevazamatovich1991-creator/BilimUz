/**
 * Admin Management of Mock Test Entitlements (Task D) — the actual
 * grant/extend/revoke UI, embedded into the existing UserDetailPage
 * (spec §5 — "integrate ... into the existing admin interface rather
 * than building a separate, disconnected dashboard"), not a standalone
 * route. Extracted into its own component (not inlined in
 * UserDetailPage.tsx) so it's independently testable, same reasoning
 * TestQuestionsListPage/QuestionFormPage already split by concern.
 *
 * Three states this panel must render correctly — spec §7.11 ("admin
 * UI handles loading, success, errors, and revocation confirmation"):
 *  - loading: a plain "Yuklanmoqda..." line, same as every other admin
 *    page in this codebase (no spinner component exists here).
 *  - success/error: via the existing global toast store (every mutation
 *    hook in useEntitlements.ts already wires this — nothing bespoke
 *    here).
 *  - revocation confirmation: the existing ConfirmDialog, same
 *    component TestFormPage's delete flow already uses.
 */
import { Fragment, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { EntitlementStatusBadge } from "@/components/entitlements/EntitlementStatusBadge";
import { usePublishedMockTestProducts } from "@/hooks/useCatalog";
import { useExtendEntitlement, useGrantEntitlement, useRevokeEntitlement, useUserEntitlements } from "@/hooks/useEntitlements";
import type { EntitlementOut } from "@/api/entitlements";

const DURATION_PRESETS = [
  { label: "30 kun", days: 30 },
  { label: "90 kun", days: 90 },
  { label: "1 yil", days: 365 },
];

function formatDate(value: string | null): string {
  if (!value) return "Muddatsiz";
  return new Date(value).toLocaleDateString("uz-UZ");
}

interface UserEntitlementsPanelProps {
  userId: string;
}

export function UserEntitlementsPanel({ userId }: UserEntitlementsPanelProps) {
  const { data: entitlements, isLoading, isError } = useUserEntitlements(userId);
  const { data: products } = usePublishedMockTestProducts();
  const grant = useGrantEntitlement(userId);
  const extend = useExtendEntitlement(userId);
  const revoke = useRevokeEntitlement(userId);

  const [productId, setProductId] = useState("");
  const [durationDays, setDurationDays] = useState<number | "custom">(30);
  const [customEndDate, setCustomEndDate] = useState("");
  const [startDate, setStartDate] = useState("");
  const [reason, setReason] = useState("");

  const [extendTargetId, setExtendTargetId] = useState<string | null>(null);
  const [extendDurationDays, setExtendDurationDays] = useState<number | "custom">(30);
  const [extendCustomEndDate, setExtendCustomEndDate] = useState("");
  const [extendReason, setExtendReason] = useState("");

  const [revokeTarget, setRevokeTarget] = useState<EntitlementOut | null>(null);

  function handleGrantSubmit(e: FormEvent) {
    e.preventDefault();
    if (!productId) return;
    grant.mutate(
      {
        user_id: userId,
        product_id: productId,
        start_date: startDate ? new Date(startDate).toISOString() : undefined,
        duration_days: durationDays === "custom" ? undefined : durationDays,
        end_date: durationDays === "custom" && customEndDate ? new Date(customEndDate).toISOString() : undefined,
        reason: reason || undefined,
      },
      {
        onSuccess: () => {
          setProductId("");
          setStartDate("");
          setReason("");
          setDurationDays(30);
          setCustomEndDate("");
        },
      },
    );
  }

  function handleExtendSubmit(e: FormEvent, entitlementId: string) {
    e.preventDefault();
    extend.mutate(
      {
        entitlementId,
        data: {
          duration_days: extendDurationDays === "custom" ? undefined : extendDurationDays,
          end_date: extendDurationDays === "custom" && extendCustomEndDate ? new Date(extendCustomEndDate).toISOString() : undefined,
          reason: extendReason || undefined,
        },
      },
      {
        onSuccess: () => {
          setExtendTargetId(null);
          setExtendReason("");
          setExtendDurationDays(30);
          setExtendCustomEndDate("");
        },
      },
    );
  }

  function handleConfirmRevoke() {
    if (!revokeTarget) return;
    revoke.mutate(
      { entitlementId: revokeTarget.id },
      { onSuccess: () => setRevokeTarget(null) },
    );
  }

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle>Mock Test ruxsatlari</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-sm text-foreground/50">Yuklanmoqda...</p>
        ) : isError ? (
          <p className="text-sm text-destructive">Ruxsatlarni yuklab bo'lmadi.</p>
        ) : (
          <div className="space-y-3">
            {entitlements && entitlements.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-foreground/50">
                      <th className="py-2 pr-3">Yo'nalish</th>
                      <th className="py-2 pr-3">Holat</th>
                      <th className="py-2 pr-3">Boshlanish</th>
                      <th className="py-2 pr-3">Tugash</th>
                      <th className="py-2 pr-3">Manba</th>
                      <th className="py-2 pr-3">Kim berdi</th>
                      <th className="py-2 pr-3">Amallar</th>
                    </tr>
                  </thead>
                  <tbody>
                    {entitlements.map((e) => (
                      <Fragment key={e.id}>
                        <tr className="border-b border-border/50">
                          <td className="py-2 pr-3">{e.subject_name ?? e.product_name}</td>
                          <td className="py-2 pr-3"><EntitlementStatusBadge status={e.effective_status} /></td>
                          <td className="py-2 pr-3">{formatDate(e.start_date)}</td>
                          <td className="py-2 pr-3">{formatDate(e.end_date)}</td>
                          <td className="py-2 pr-3">{e.source === "admin_grant" ? "Administrator" : "Sotib olingan"}</td>
                          <td className="py-2 pr-3">{e.granted_by_name ?? "—"}</td>
                          <td className="py-2 pr-3">
                            <div className="flex gap-2">
                              {e.effective_status !== "revoked" ? (
                                <Button
                                  type="button" size="sm" variant="outline"
                                  onClick={() => setExtendTargetId(extendTargetId === e.id ? null : e.id)}
                                >
                                  Cho'zish
                                </Button>
                              ) : null}
                              {e.effective_status === "active" || e.effective_status === "scheduled" ? (
                                <Button type="button" size="sm" variant="destructive" onClick={() => setRevokeTarget(e)}>
                                  Bekor qilish
                                </Button>
                              ) : null}
                            </div>
                          </td>
                        </tr>
                        {extendTargetId === e.id ? (
                          <tr className="border-b border-border/50 bg-muted/30">
                            <td colSpan={7} className="py-3">
                              <form onSubmit={(ev) => handleExtendSubmit(ev, e.id)} className="flex flex-wrap items-end gap-2">
                                <div>
                                  <label className="mb-1 block text-xs font-medium text-foreground">Muddat</label>
                                  <select
                                    value={extendDurationDays}
                                    onChange={(ev) => setExtendDurationDays(ev.target.value === "custom" ? "custom" : Number(ev.target.value))}
                                    className="rounded-md border border-border bg-background px-2 py-1.5 text-xs"
                                  >
                                    {DURATION_PRESETS.map((p) => <option key={p.days} value={p.days}>{p.label}</option>)}
                                    <option value="custom">Boshqa sana</option>
                                  </select>
                                </div>
                                {extendDurationDays === "custom" ? (
                                  <div>
                                    <label className="mb-1 block text-xs font-medium text-foreground">Yangi tugash sanasi</label>
                                    <Input type="date" value={extendCustomEndDate} onChange={(ev) => setExtendCustomEndDate(ev.target.value)} className="h-8 text-xs" required />
                                  </div>
                                ) : null}
                                <div className="flex-1 min-w-[160px]">
                                  <label className="mb-1 block text-xs font-medium text-foreground">Sabab (ixtiyoriy)</label>
                                  <Input value={extendReason} onChange={(ev) => setExtendReason(ev.target.value)} className="h-8 text-xs" />
                                </div>
                                <Button type="submit" size="sm" disabled={extend.isPending}>
                                  {extend.isPending ? "..." : "Tasdiqlash"}
                                </Button>
                              </form>
                            </td>
                          </tr>
                        ) : null}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-foreground/50">Bu foydalanuvchida hozircha Mock Test ruxsatlari yo'q.</p>
            )}

            <form onSubmit={handleGrantSubmit} className="mt-4 space-y-3 border-t border-border pt-4">
              <h3 className="text-sm font-semibold text-foreground">Yangi ruxsat berish</h3>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="grant-product" className="mb-1 block text-sm font-medium text-foreground">Fan / yo'nalish</label>
                  <select
                    id="grant-product"
                    value={productId}
                    onChange={(e) => setProductId(e.target.value)}
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                    required
                  >
                    <option value="">Tanlang...</option>
                    {products?.items.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                  {products && products.items.length === 0 ? (
                    <p className="mt-1 text-xs text-foreground/50">
                      Hozircha e'lon qilingan Mock Test mahsuloti yo'q — avval Katalog bo'limida yarating.
                    </p>
                  ) : null}
                </div>
                <div>
                  <label htmlFor="grant-duration" className="mb-1 block text-sm font-medium text-foreground">Muddat</label>
                  <select
                    id="grant-duration"
                    value={durationDays}
                    onChange={(e) => setDurationDays(e.target.value === "custom" ? "custom" : Number(e.target.value))}
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  >
                    {DURATION_PRESETS.map((p) => <option key={p.days} value={p.days}>{p.label}</option>)}
                    <option value="custom">Boshqa sana / muddatsiz</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="grant-start" className="mb-1 block text-sm font-medium text-foreground">Boshlanish sanasi (ixtiyoriy)</label>
                  <Input id="grant-start" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
                </div>
                {durationDays === "custom" ? (
                  <div>
                    <label htmlFor="grant-end" className="mb-1 block text-sm font-medium text-foreground">Tugash sanasi (bo'sh — muddatsiz)</label>
                    <Input id="grant-end" type="date" value={customEndDate} onChange={(e) => setCustomEndDate(e.target.value)} />
                  </div>
                ) : null}
              </div>
              <div>
                <label htmlFor="grant-reason" className="mb-1 block text-sm font-medium text-foreground">Sabab (ixtiyoriy)</label>
                <Input id="grant-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Masalan: qo'llab-quvvatlash xizmati tomonidan tasdiqlangan" />
              </div>
              <Button type="submit" disabled={grant.isPending || !productId}>
                {grant.isPending ? "Berilmoqda..." : "Ruxsat berish"}
              </Button>
            </form>
          </div>
        )}
      </CardContent>

      <ConfirmDialog
        open={!!revokeTarget}
        title="Ruxsatni bekor qilish"
        description={`"${revokeTarget?.subject_name ?? revokeTarget?.product_name}" yo'nalishi bo'yicha ruxsatni bekor qilasizmi? Bu amalni orqaga qaytarib bo'lmaydi.`}
        confirmLabel="Ha, bekor qilish"
        cancelLabel="Yopish"
        isConfirming={revoke.isPending}
        onConfirm={handleConfirmRevoke}
        onCancel={() => setRevokeTarget(null)}
      />
    </Card>
  );
}
