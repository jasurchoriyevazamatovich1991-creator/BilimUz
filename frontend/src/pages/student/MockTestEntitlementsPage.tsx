/**
 * Student/Applicant self-view of their own Mock Test entitlements
 * (Admin Management of Mock Test Entitlements, Task D, spec §5 —
 * "add a user-facing view ... do not expose administrative controls to
 * ordinary users"). Read-only: no grant/extend/revoke actions anywhere
 * on this page, unlike UserEntitlementsPanel.tsx which the admin side
 * uses. Reuses the exact same GET /entitlements/me endpoint and
 * EntitlementOut shape — the only difference is this page never
 * imports the mutation hooks at all, so there is no code path here
 * that could call grant/extend/revoke even by mistake.
 */
import { EntitlementStatusBadge } from "@/components/entitlements/EntitlementStatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/layout/ErrorState";
import { useMyEntitlements } from "@/hooks/useEntitlements";

function formatDate(value: string | null): string {
  if (!value) return "Muddatsiz";
  return new Date(value).toLocaleDateString("uz-UZ");
}

export function MockTestEntitlementsPage() {
  const { data: entitlements, isLoading, isError } = useMyEntitlements();

  if (isError) return <ErrorState title="Mock Test ruxsatlari" />;

  return (
    <div className="max-w-3xl">
      <h1 className="mb-4 text-xl font-semibold text-foreground">Mening Mock Test ruxsatlarim</h1>

      <Card>
        <CardHeader>
          <CardTitle>Fan va yo'nalishlar bo'yicha kirish huquqi</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-foreground/50">Yuklanmoqda...</p>
          ) : entitlements && entitlements.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-foreground/50">
                    <th className="py-2 pr-3">Yo'nalish</th>
                    <th className="py-2 pr-3">Holat</th>
                    <th className="py-2 pr-3">Boshlanish</th>
                    <th className="py-2 pr-3">Tugash</th>
                  </tr>
                </thead>
                <tbody>
                  {entitlements.map((e) => (
                    <tr key={e.id} className="border-b border-border/50">
                      <td className="py-2 pr-3">{e.subject_name ?? e.product_name}</td>
                      <td className="py-2 pr-3"><EntitlementStatusBadge status={e.effective_status} /></td>
                      <td className="py-2 pr-3">{formatDate(e.start_date)}</td>
                      <td className="py-2 pr-3">{formatDate(e.end_date)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-foreground/50">
              Sizda hozircha Mock Test ruxsatlari yo'q. Kirish huquqini olish uchun administratsiya bilan bog'laning.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
