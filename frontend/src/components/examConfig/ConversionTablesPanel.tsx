/**
 * Task 4 — a section's versioned raw-to-scaled conversion tables
 * (Admin/Super Admin). Publishing always creates a NEW version; earlier
 * versions stay visible and keep scoring the results created with them.
 * The backend validates ranges, steps, monotonicity, duplicates and gaps
 * and answers 422 with a specific message (shown as a toast).
 *
 * Task 7 — every table states its provenance. "Rasmiy amaliy test" is
 * offered only for SAT. IELTS and GRE tables can only be estimates or
 * unverified.
 *
 * Task 8 — for an official SAT practice test the admin only picks the form:
 * the exact lower/upper values come from the verified College Board dataset
 * on the server (nothing is typed by hand). Documented source anomalies
 * (e.g. Practice Test 6, R&W raw 41) are listed as warnings.
 */
import { useState, useId, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { useConversionTables, usePublishConversionTable } from "@/hooks/useExamConfig";
import type { ConversionMethod, ConversionTableCreateRequest, ConversionTableOut, ConversionType } from "@/api/examConfig";
import { SAT_PRACTICE_FORMS, SCORE_COMPONENTS, parseRangeTableText, parseTableText } from "@/lib/scaledScoring";

interface ConversionTablesPanelProps {
  sectionId: string;
  component: string;
  /** routing_variant values of this section's modules (adaptive sections). */
  variants: string[];
}

const TYPE_LABELS: Record<ConversionType, string> = {
  official_practice_test: "Rasmiy amaliy test jadvali",
  estimate: "Taxminiy",
  unverified: "Tasdiqlanmagan",
};

function entryText(e: ConversionTableOut["entries"][number]): string {
  return e.lower != null ? `${e.raw}→${e.lower}–${e.upper}` : `${e.raw}→${e.scaled}`;
}

export function ConversionTablesPanel({ sectionId, component, variants }: ConversionTablesPanelProps) {
  const id = useId();
  const { data: tables, isLoading, isError } = useConversionTables(sectionId);
  const publish = usePublishConversionTable(sectionId);
  const info = SCORE_COMPONENTS[component];
  const officialAllowed = info?.profile === "sat";

  const [ctype, setCtype] = useState<ConversionType>("unverified");
  const [method, setMethod] = useState<ConversionMethod>("exact");
  const [variant, setVariant] = useState("");
  const [testForm, setTestForm] = useState("");
  const [sourceTitle, setSourceTitle] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [verifiedAt, setVerifiedAt] = useState("");
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);

  const isOfficial = ctype === "official_practice_test";
  const effectiveMethod: ConversionMethod = isOfficial ? "range" : method;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (isOfficial) {
      if (!testForm) {
        setError("Rasmiy jadval uchun amaliy testni tanlang");
        return;
      }
      setError(null);
      publish.mutate({ method: "range", conversion_type: "official_practice_test", test_form: testForm });
      return;
    }
    const parsed = effectiveMethod === "range" ? parseRangeTableText(text) : parseTableText(text);
    if ("error" in parsed) {
      setError(parsed.error);
      return;
    }
    setError(null);
    const body: ConversionTableCreateRequest = { method: effectiveMethod, entries: parsed.entries };
    if (variant) body.routing_variant = variant;
    if (ctype !== "unverified") body.conversion_type = ctype;
    if (sourceTitle.trim()) body.source_title = sourceTitle.trim();
    if (sourceUrl.trim()) body.source_url = sourceUrl.trim();
    if (verifiedAt) body.source_verified_at = verifiedAt;
    publish.mutate(body, { onSuccess: () => setText("") });
  }

  return (
    <div className="mt-3 space-y-3 border-t border-border pt-3 pl-3" data-testid={`conversion-tables-${sectionId}`}>
      <p className="text-xs text-foreground/60">
        {info?.label}: shkala {info?.range}. "exact" — 0 dan eng katta xom ballgacha har bir butun qiymat kiritiladi;
        "linear" — faqat kiritilgan nuqtalar orasida interpolyatsiya qilinadi, tashqarisi hisoblanmaydi;
        "range" — har bir xom ball uchun pastki va yuqori ball (College Board scoring guide'lari kabi).
      </p>
      {info?.profile === "gre" ? (
        <p className="text-xs text-amber-700">
          ETS GRE ballarini equating orqali hisoblaydi va ochiq raw→scaled jadval chop etmaydi — bu yerdagi har qanday jadval faqat taxminiy.
        </p>
      ) : null}
      {info?.profile === "ielts" ? (
        <p className="text-xs text-amber-700">
          IELTS rasmiy to'liq jadval chop etmaydi. Jadval bo'lmasa IELTS.org'dagi o'rtacha ko'rsatkichlar asosida taxminiy oraliq ko'rsatiladi.
        </p>
      ) : null}

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
              {t.entries.length > 0 ? ` (${entryText(t.entries[0])} … ${entryText(t.entries[t.entries.length - 1])})` : ""}
              {t.is_current ? <span className="ml-2 rounded bg-primary/10 px-1.5 text-xs text-primary">joriy</span> : null}
              <span className="block text-xs text-foreground/60" data-testid="table-provenance">
                {TYPE_LABELS[t.conversion_type ?? "unverified"]}
                {t.test_form ? ` · ${SAT_PRACTICE_FORMS.find((f) => f.id === t.test_form)?.label ?? t.test_form}` : ""}
                {t.source_url ? (
                  <>
                    {" · "}
                    <a href={t.source_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                      {t.source_title ?? "manba"}
                    </a>
                  </>
                ) : t.source_title ? ` · ${t.source_title}` : ""}
                {t.source_verified_at ? ` · tekshirilgan: ${t.source_verified_at}` : ""}
                {t.source_version ? ` · ${t.source_version}` : ""}
              </span>
              {(t.source_anomalies ?? []).map((note) => (
                <span key={note} role="note" className="block text-xs text-amber-700" data-testid="table-anomaly">⚠ {note}</span>
              ))}
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={handleSubmit} className="space-y-2">
        <div className="flex flex-wrap gap-2">
          <div>
            <label htmlFor={`${id}-type`} className="mb-1 block text-xs font-medium text-foreground/70">Jadval turi</label>
            <select
              id={`${id}-type`}
              value={ctype}
              onChange={(e) => setCtype(e.target.value as ConversionType)}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              <option value="unverified">{TYPE_LABELS.unverified}</option>
              <option value="estimate">{TYPE_LABELS.estimate}</option>
              {officialAllowed ? <option value="official_practice_test">{TYPE_LABELS.official_practice_test}</option> : null}
            </select>
          </div>
          {isOfficial ? (
            <div>
              <label htmlFor={`${id}-form`} className="mb-1 block text-xs font-medium text-foreground/70">Amaliy test</label>
              <select
                id={`${id}-form`}
                value={testForm}
                onChange={(e) => setTestForm(e.target.value)}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm"
              >
                <option value="">— tanlang</option>
                {SAT_PRACTICE_FORMS.map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
              </select>
            </div>
          ) : (
            <div>
              <label htmlFor={`${id}-method`} className="mb-1 block text-xs font-medium text-foreground/70">Usul</label>
              <select
                id={`${id}-method`}
                value={method}
                onChange={(e) => setMethod(e.target.value as ConversionMethod)}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm"
              >
                <option value="exact">exact</option>
                <option value="linear">linear</option>
                <option value="range">range</option>
              </select>
            </div>
          )}
          {variants.length > 0 && !isOfficial ? (
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
        {isOfficial ? (
          <p className="text-xs text-foreground/60" data-testid="official-import-note">
            Qiymatlar kiritilmaydi: tanlangan testning rasmiy College Board scoring guide'idagi jadval (R&W 0–66, Math 0–54,
            pastki–yuqori oraliq) tekshirilgan manbadan aynan olinadi va manba havolasi qo'yiladi. Bo'limda shu formaning
            savollar soni (R&W 66, Math 54, har biri 1 ball) bo'lishi kerak; adaptiv bo'limlarga qo'llanmaydi. Natija talabaga
            "amaliy test bo'yicha taxminiy oraliq — rasmiy SAT natijasi emas" deb ko'rsatiladi.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <div>
              <label htmlFor={`${id}-stitle`} className="mb-1 block text-xs font-medium text-foreground/70">Manba nomi (ixtiyoriy)</label>
              <input id={`${id}-stitle`} value={sourceTitle} maxLength={300} onChange={(e) => setSourceTitle(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" />
            </div>
            <div>
              <label htmlFor={`${id}-surl`} className="mb-1 block text-xs font-medium text-foreground/70">Manba havolasi (ixtiyoriy)</label>
              <input id={`${id}-surl`} type="url" value={sourceUrl} maxLength={500} onChange={(e) => setSourceUrl(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" />
            </div>
          </div>
        )}
        {!isOfficial ? (
          <>
            <div>
              <label htmlFor={`${id}-verified`} className="mb-1 block text-xs font-medium text-foreground/70">Manba tekshirilgan sana (ixtiyoriy)</label>
              <input id={`${id}-verified`} type="date" value={verifiedAt} onChange={(e) => setVerifiedAt(e.target.value)}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm" />
            </div>
            <div>
              <label htmlFor={`${id}-rows`} className="mb-1 block text-xs font-medium text-foreground/70">
                {effectiveMethod === "range" ? 'Qatorlar: har qatorda "xom ball, pastki, yuqori"' : 'Qatorlar: har qatorda "xom ball, shkala balli"'}
              </label>
              <textarea
                id={`${id}-rows`}
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={6}
                placeholder={effectiveMethod === "range" ? "0, 200, 200\n1, 200, 210" : "0, 200\n1, 210\n2, 230"}
                className="w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-sm"
              />
            </div>
          </>
        ) : null}
        {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
        <Button type="submit" disabled={publish.isPending}>
          {publish.isPending ? "..." : isOfficial ? "Rasmiy jadvalni import qilish" : "Yangi versiyani e'lon qilish"}
        </Button>
      </form>
    </div>
  );
}
