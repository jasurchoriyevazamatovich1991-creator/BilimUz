/**
 * Task 4 — a section's versioned raw-to-scaled conversion tables
 * (Admin/Super Admin). Publishing always creates a NEW version; earlier
 * versions stay visible and keep scoring the results created with them.
 * The backend validates ranges, steps, monotonicity, duplicates and gaps
 * and answers 422 with a specific message (shown as a toast).
 */
import { useState, useId, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { useConversionTables, usePublishConversionTable } from "@/hooks/useExamConfig";
import { SCORE_COMPONENTS, parseTableText } from "@/lib/scaledScoring";

interface ConversionTablesPanelProps {
  sectionId: string;
  component: string;
  /** routing_variant values of this section's modules (adaptive sections). */
  variants: string[];
}

export function ConversionTablesPanel({ sectionId, component, variants }: ConversionTablesPanelProps) {
  const id = useId();
  const { data: tables, isLoading, isError } = useConversionTables(sectionId);
  const publish = usePublishConversionTable(sectionId);
  const [method, setMethod] = useState<"exact" | "linear">("exact");
  const [variant, setVariant] = useState("");
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const info = SCORE_COMPONENTS[component];

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const parsed = parseTableText(text);
    if ("error" in parsed) {
      setError(parsed.error);
      return;
    }
    setError(null);
    publish.mutate(
      { method, entries: parsed.entries, ...(variant ? { routing_variant: variant } : {}) },
      { onSuccess: () => setText("") },
    );
  }

  return (
    <div className="mt-3 space-y-3 border-t border-border pt-3 pl-3" data-testid={`conversion-tables-${sectionId}`}>
      <p className="text-xs text-foreground/60">
        {info?.label}: shkala {info?.range}. "exact" — 0 dan eng katta xom ballgacha har bir butun qiymat kiritiladi;
        "linear" — faqat kiritilgan nuqtalar orasida interpolyatsiya qilinadi, tashqarisi hisoblanmaydi.
      </p>

      {isLoading ? (
        <p className="text-sm text-foreground/50">Yuklanmoqda...</p>
      ) : isError ? (
        <p className="text-sm text-destructive">Jadvallarni yuklab bo'lmadi</p>
      ) : (tables ?? []).length === 0 ? (
        <p className="text-sm text-foreground/50">Hali jadval yo'q — bu bo'lim uchun shkala balli hisoblanmaydi.</p>
      ) : (
        <ul className="space-y-1">
          {(tables ?? []).map((t) => (
            <li key={t.id} className="text-sm text-foreground">
              <span className="font-medium">v{t.version}</span>
              {t.routing_variant ? ` · variant: ${t.routing_variant}` : ""} · {t.method} · {t.entries.length} qator
              {t.entries.length > 0 ? ` (${t.entries[0].raw}→${t.entries[0].scaled} … ${t.entries[t.entries.length - 1].raw}→${t.entries[t.entries.length - 1].scaled})` : ""}
              {t.is_current ? <span className="ml-2 rounded bg-primary/10 px-1.5 text-xs text-primary">joriy</span> : null}
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={handleSubmit} className="space-y-2">
        <div className="flex flex-wrap gap-2">
          <div>
            <label htmlFor={`${id}-method`} className="mb-1 block text-xs font-medium text-foreground/70">Usul</label>
            <select
              id={`${id}-method`}
              value={method}
              onChange={(e) => setMethod(e.target.value as "exact" | "linear")}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              <option value="exact">exact</option>
              <option value="linear">linear</option>
            </select>
          </div>
          {variants.length > 0 ? (
            <div>
              <label htmlFor={`${id}-variant`} className="mb-1 block text-xs font-medium text-foreground/70">Routing variant</label>
              <select
                id={`${id}-variant`}
                value={variant}
                onChange={(e) => setVariant(e.target.value)}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm"
              >
                <option value="">— (variantsiz)</option>
                {variants.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>
          ) : null}
        </div>
        <div>
          <label htmlFor={`${id}-rows`} className="mb-1 block text-xs font-medium text-foreground/70">
            Qatorlar: har qatorda "xom ball, shkala balli"
          </label>
          <textarea
            id={`${id}-rows`}
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={6}
            placeholder={"0, 200\n1, 210\n2, 230"}
            className="w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-sm"
          />
        </div>
        {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
        <Button type="submit" disabled={publish.isPending}>{publish.isPending ? "..." : "Yangi versiyani e'lon qilish"}</Button>
      </form>
    </div>
  );
}
