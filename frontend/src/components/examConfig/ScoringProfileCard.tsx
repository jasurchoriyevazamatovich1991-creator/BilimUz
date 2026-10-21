/**
 * Task 4 — choose a test's exam scoring profile (Admin/Super Admin; the
 * whole Exam Configuration page is already restricted to them). An
 * explicit choice: the profile is never inferred from the test title.
 */
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useSetScoringProfile } from "@/hooks/useExamConfig";
import { SCORING_PROFILE_LABELS, type ScoringProfile } from "@/lib/scaledScoring";

interface ScoringProfileCardProps {
  testId: string;
  current: ScoringProfile | null;
}

export function ScoringProfileCard({ testId, current }: ScoringProfileCardProps) {
  const [value, setValue] = useState<string>(current ?? "");
  const setProfile = useSetScoringProfile(testId);
  useEffect(() => setValue(current ?? ""), [current]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Ballash profili</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-xs text-foreground/60">
          Profil tanlanmasa test oddiy foiz bilan baholanadi. IELTS/SAT/GRE profili tanlansa, bo'limlarga komponent
          belgilanadi va shkala ballari admin kiritgan konversiya jadvallaridan hisoblanadi — rasmiy jadvallar
          avtomatik qo'shilmaydi.
        </p>
        <div className="flex flex-wrap items-end gap-2">
          <div>
            <label htmlFor="scoringProfile" className="mb-1 block text-xs font-medium text-foreground/70">Profil</label>
            <select
              id="scoringProfile"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              <option value="">Oddiy foiz (profil yo'q)</option>
              {(Object.keys(SCORING_PROFILE_LABELS) as ScoringProfile[]).map((p) => (
                <option key={p} value={p}>{SCORING_PROFILE_LABELS[p]}</option>
              ))}
            </select>
          </div>
          <Button
            type="button"
            disabled={setProfile.isPending || value === (current ?? "")}
            onClick={() => setProfile.mutate(value ? (value as ScoringProfile) : null)}
          >
            {setProfile.isPending ? "..." : "Profilni saqlash"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
