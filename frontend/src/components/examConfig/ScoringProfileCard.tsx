/**
 * Task 4 — choose a test's exam scoring profile (Admin/Super Admin; the
 * whole Exam Configuration page is already restricted to them). An
 * explicit choice: the profile is never inferred from the test title.
 *
 * Task 7 — for IELTS also the module (Academic / General Training): the
 * two use different official Reading reference points.
 */
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useSetScoringProfile } from "@/hooks/useExamConfig";
import type { IeltsModule } from "@/api/examConfig";
import { IELTS_MODULE_LABELS, SCORING_PROFILE_LABELS, type ScoringProfile } from "@/lib/scaledScoring";

interface ScoringProfileCardProps {
  testId: string;
  current: ScoringProfile | null;
  currentIeltsModule?: IeltsModule | null;
}

export function ScoringProfileCard({ testId, current, currentIeltsModule = null }: ScoringProfileCardProps) {
  const [value, setValue] = useState<string>(current ?? "");
  const [module, setModule] = useState<string>(currentIeltsModule ?? "");
  const setProfile = useSetScoringProfile(testId);
  useEffect(() => setValue(current ?? ""), [current]);
  useEffect(() => setModule(currentIeltsModule ?? ""), [currentIeltsModule]);

  const isIelts = value === "ielts";
  const unchanged = value === (current ?? "") && (!isIelts || module === (currentIeltsModule ?? ""));

  function save() {
    const profile = value ? (value as ScoringProfile) : null;
    if (isIelts) setProfile.mutate({ profile, ieltsModule: module ? (module as IeltsModule) : null });
    else setProfile.mutate(profile);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Ballash profili</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-xs text-foreground/60">
          Profil tanlanmasa test oddiy foiz bilan baholanadi. IELTS/SAT/GRE profili tanlansa, bo'limlarga komponent
          belgilanadi. Rasmiy jadval ma'lumotlari avtomatik qo'shilmaydi: SAT amaliy test jadvali rasmiy scoring
          guide'dan kiritiladi; IELTS Listening/Reading uchun jadval bo'lmasa faqat IELTS.org'dagi o'rtacha
          ko'rsatkichlar asosida taxminiy oraliq chiqadi; GRE uchun ETS jadval chop etmaydi.
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
          {isIelts ? (
            <div>
              <label htmlFor="ieltsModule" className="mb-1 block text-xs font-medium text-foreground/70">IELTS moduli</label>
              <select
                id="ieltsModule"
                value={module}
                onChange={(e) => setModule(e.target.value)}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm"
              >
                <option value="">— (tanlanmagan)</option>
                {(Object.keys(IELTS_MODULE_LABELS) as IeltsModule[]).map((m) => (
                  <option key={m} value={m}>{IELTS_MODULE_LABELS[m]}</option>
                ))}
              </select>
            </div>
          ) : null}
          <Button type="button" disabled={setProfile.isPending || unchanged} onClick={save}>
            {setProfile.isPending ? "..." : "Profilni saqlash"}
          </Button>
        </div>
        {isIelts && !module ? (
          <p className="text-xs text-amber-700">Modul tanlanmasa Reading uchun taxminiy band hisoblanmaydi (Academic va General Training ko'rsatkichlari farq qiladi).</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
