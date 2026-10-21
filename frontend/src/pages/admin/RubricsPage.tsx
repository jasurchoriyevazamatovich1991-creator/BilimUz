/**
 * Task 5 — admin management of grading rubrics (Admin/Super Admin can
 * publish; the backend enforces it). Rubrics are versioned and immutable:
 * publishing creates a new version, and grades already given keep the
 * version they used. No official rubric is pre-filled; "Tasdiqlangan"
 * should only be ticked for a rubric checked against a validated source,
 * otherwise every score made with it is shown as provisional.
 */
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ManualComponent } from "@/api/grading";
import { useCreateRubric, useRubrics } from "@/hooks/useGrading";
import { MANUAL_COMPONENT_LABELS } from "@/lib/grading";

interface CriterionRow { key: string; label: string; min: string; max: string; step: string; weight: string }

const EMPTY_ROW: CriterionRow = { key: "", label: "", min: "0", max: "9", step: "1", weight: "1" };
const COMPONENTS = Object.keys(MANUAL_COMPONENT_LABELS) as ManualComponent[];

export function RubricsPage() {
  const [component, setComponent] = useState<ManualComponent>("ielts_writing");
  const { data: rubrics, isLoading, isError } = useRubrics(component);
  const create = useCreateRubric();
  const [name, setName] = useState("");
  const [rows, setRows] = useState<CriterionRow[]>([{ ...EMPTY_ROW }]);
  const [rounding, setRounding] = useState<"half_up" | "floor">("half_up");
  const [instructions, setInstructions] = useState("");
  const [validated, setValidated] = useState(false);

  const setRow = (i: number, patch: Partial<CriterionRow>) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    create.mutate(
      {
        score_component: component, name: name.trim(), rounding, is_validated: validated,
        instructions: instructions.trim() || undefined,
        criteria: rows.map((r) => ({ ...r, key: r.key.trim(), label: r.label.trim() })),
      },
      { onSuccess: () => { setName(""); setRows([{ ...EMPTY_ROW }]); setInstructions(""); setValidated(false); } },
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-foreground">Baholash rubrikalari</h1>
      <div>
        <label htmlFor="rubricComponent" className="mb-1 block text-xs font-medium text-foreground/70">Komponent</label>
        <select id="rubricComponent" value={component} onChange={(e) => setComponent(e.target.value as ManualComponent)}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm">
          {COMPONENTS.map((c) => <option key={c} value={c}>{MANUAL_COMPONENT_LABELS[c]}</option>)}
        </select>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Versiyalar</CardTitle></CardHeader>
        <CardContent>
          {isLoading ? <p className="text-sm text-foreground/50">Yuklanmoqda...</p>
            : isError ? <p className="text-sm text-destructive" role="alert">Rubrikalarni yuklab bo'lmadi</p>
            : (rubrics ?? []).length === 0 ? <p className="text-sm text-foreground/50">Bu komponent uchun rubrika yo'q — baholash boshlanmaydi.</p>
            : (
              <ul className="space-y-2">
                {(rubrics ?? []).map((r) => (
                  <li key={r.id} className="text-sm text-foreground">
                    <span className="font-medium">v{r.version} · {r.name}</span>
                    {r.is_current ? <span className="ml-2 rounded bg-primary/10 px-1.5 text-xs text-primary">joriy</span> : null}
                    {!r.is_validated ? <span className="ml-2 text-xs text-amber-700">tasdiqlanmagan</span> : null}
                    <span className="block text-xs text-foreground/60">
                      {r.criteria.map((c) => `${c.label} ${c.min}–${c.max}${c.weight !== "1" ? ` ×${c.weight}` : ""}`).join(" · ")} · {r.rounding}
                    </span>
                  </li>
                ))}
              </ul>
            )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Yangi versiya</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label htmlFor="rubricName" className="mb-1 block text-xs font-medium text-foreground/70">Nomi</label>
              <input id="rubricName" required maxLength={150} value={name} onChange={(e) => setName(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" />
            </div>
            {rows.map((r, i) => (
              <div key={i} className="grid grid-cols-2 gap-2 sm:grid-cols-[1fr_2fr_repeat(4,5rem)_auto]">
                <input aria-label={`Mezon ${i + 1} kaliti`} placeholder="key" value={r.key} onChange={(e) => setRow(i, { key: e.target.value })}
                  className="rounded-md border border-border bg-background px-2 py-1 text-sm" />
                <input aria-label={`Mezon ${i + 1} nomi`} placeholder="Nomi" value={r.label} onChange={(e) => setRow(i, { label: e.target.value })}
                  className="rounded-md border border-border bg-background px-2 py-1 text-sm" />
                {(["min", "max", "step", "weight"] as const).map((f) => (
                  <input key={f} aria-label={`Mezon ${i + 1} ${f}`} placeholder={f} value={r[f]} inputMode="decimal"
                    onChange={(e) => setRow(i, { [f]: e.target.value })}
                    className="rounded-md border border-border bg-background px-2 py-1 text-sm" />
                ))}
                <button type="button" aria-label={`Mezon ${i + 1} ni o'chirish`} disabled={rows.length === 1}
                  onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))} className="text-sm text-destructive disabled:opacity-40">×</button>
              </div>
            ))}
            {rows.length < 10 ? (
              <button type="button" onClick={() => setRows((rs) => [...rs, { ...EMPTY_ROW }])} className="text-sm text-primary hover:underline">+ Mezon qo'shish</button>
            ) : null}
            <div className="flex flex-wrap gap-4">
              <div>
                <label htmlFor="rubricRounding" className="mb-1 block text-xs font-medium text-foreground/70">Yaxlitlash</label>
                <select id="rubricRounding" value={rounding} onChange={(e) => setRounding(e.target.value as "half_up" | "floor")}
                  className="rounded-md border border-border bg-background px-3 py-2 text-sm">
                  <option value="half_up">half_up (yaqiniga, .5 yuqoriga)</option>
                  <option value="floor">floor (pastga)</option>
                </select>
              </div>
              <label className="flex items-center gap-2 self-end text-sm text-foreground">
                <input type="checkbox" checked={validated} onChange={(e) => setValidated(e.target.checked)} className="accent-primary" />
                Tasdiqlangan manbaga mos (aks holda ballar provisional)
              </label>
            </div>
            <div>
              <label htmlFor="rubricInstructions" className="mb-1 block text-xs font-medium text-foreground/70">Baholovchiga ko'rsatma (ixtiyoriy)</label>
              <textarea id="rubricInstructions" rows={3} maxLength={10000} value={instructions} onChange={(e) => setInstructions(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" />
            </div>
            <Button type="submit" disabled={create.isPending}>{create.isPending ? "..." : "Versiyani e'lon qilish"}</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
