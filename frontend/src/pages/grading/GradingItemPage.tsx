/**
 * Task 5 — grade one response with its rubric. Drafts can be saved and
 * resumed; finalizing releases the grade to the student; a finalized grade
 * is corrected only through an explicit revision with a reason. The full
 * history (including superseded grades) is shown. The backend validates
 * every score and owns grader/status/rubric fields.
 */
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FormulaText } from "@/components/questions/FormulaText";
import { ApiError } from "@/api/client";
import { gradingApi, type ReviewOut } from "@/api/grading";
import { useFinalizeReview, useReviseReview, useSaveDraft, useSubmission } from "@/hooks/useGrading";
import { MANUAL_COMPONENT_LABELS, REVIEW_STATUS_LABELS, criterionError } from "@/lib/grading";

/** Task 6 — loads the Speaking recording through the permission-checked
 * grading endpoint as a Blob (no public/signed URL) only when asked. */
function ResponseAudio({ attemptId, questionId }: { attemptId: string; questionId: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);

  async function load() {
    setLoading(true);
    setFailed(null);
    try {
      setUrl(URL.createObjectURL(await gradingApi.getAudio(attemptId, questionId)));
    } catch (err) {
      setFailed(err instanceof ApiError && err.status === 403 ? "Audio tinglash uchun ruxsat yo'q." : "Audioni yuklab bo'lmadi.");
    } finally {
      setLoading(false);
    }
  }

  if (url) return <audio controls src={url} aria-label="Talabaning og'zaki javobi" className="mb-3 w-full" data-testid="response-audio" />;
  return (
    <div className="mb-3">
      <Button type="button" variant="outline" onClick={load} disabled={loading}>{loading ? "Yuklanmoqda..." : "Audio javobni tinglash"}</Button>
      {failed ? <p role="alert" className="mt-1 text-sm text-destructive">{failed}</p> : null}
    </div>
  );
}

export function GradingItemPage({ basePath = "/admin" }: { basePath?: string }) {
  const { attemptId = "", questionId = "" } = useParams<{ attemptId: string; questionId: string }>();
  const navigate = useNavigate();
  const { data, isLoading, isError, error } = useSubmission(attemptId, questionId);
  const saveDraft = useSaveDraft(attemptId, questionId);
  const finalize = useFinalizeReview(attemptId, questionId);
  const revise = useReviseReview(attemptId, questionId);

  const draft = data?.reviews.find((r) => r.status === "draft") ?? null;
  const finalized = data?.reviews.find((r) => r.status === "finalized") ?? null;
  const editable = !!data?.rubric && (draft !== null || finalized === null);

  const [scores, setScores] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState("");
  const [notes, setNotes] = useState("");
  const [reason, setReason] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  // Load the open draft (or nothing) into the form whenever it changes.
  useEffect(() => {
    setScores(draft ? { ...draft.criterion_scores } : {});
    setFeedback(draft?.feedback ?? "");
    setNotes(draft?.internal_notes ?? "");
  }, [draft?.id, draft?.updated_at]); // eslint-disable-line react-hooks/exhaustive-deps

  const criteria = useMemo(() => data?.rubric?.criteria ?? [], [data?.rubric]);

  if (isLoading) return <p className="text-sm text-foreground/50">Yuklanmoqda...</p>;
  if (error instanceof ApiError && error.status === 403) {
    return <p className="text-sm text-destructive" role="alert">Sizda javoblarni baholash ruxsati (GRADE_SUBMISSIONS) yo'q.</p>;
  }
  if (isError || !data) return <p className="text-sm text-destructive" role="alert">Javobni yuklab bo'lmadi</p>;

  function validate(requireAll: boolean): Record<string, string> | null {
    const out: Record<string, string> = {};
    for (const c of criteria) {
      const v = (scores[c.key] ?? "").trim();
      const err = criterionError(c, v);
      if (err) { setLocalError(err); return null; }
      if (v !== "") out[c.key] = v;
      else if (requireAll) { setLocalError(`${c.label}: ball kiritilmagan`); return null; }
    }
    setLocalError(null);
    return out;
  }

  function handleSave() {
    const valid = validate(false);
    if (valid) saveDraft.mutate({ criterion_scores: valid, feedback: feedback || null, internal_notes: notes || null });
  }

  function handleFinalize() {
    const valid = validate(true);
    if (!valid) return;
    // Persist the visible form first, then finalize that draft.
    saveDraft.mutate(
      { criterion_scores: valid, feedback: feedback || null, internal_notes: notes || null },
      { onSuccess: () => finalize.mutate(undefined) },
    );
  }

  return (
    <div className="space-y-4">
      <button type="button" onClick={() => navigate(`${basePath}/grading`)} className="text-sm text-primary hover:underline">← Navbatga qaytish</button>
      <div>
        <h1 className="text-xl font-semibold text-foreground">{data.test_title} · {data.section_name}</h1>
        <p className="text-sm text-foreground/60">{MANUAL_COMPONENT_LABELS[data.score_component]}</p>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Topshiriq</CardTitle></CardHeader>
        <CardContent><FormulaText html={data.question_text} className="block text-sm text-foreground" /></CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Talaba javobi</CardTitle></CardHeader>
        <CardContent>
          {data.has_audio ? (
            <ResponseAudio attemptId={attemptId} questionId={questionId} />
          ) : data.score_component === "ielts_speaking" ? (
            <p className="mb-2 text-xs text-foreground/50">Talaba audio yozuv yubormagan — faqat matnli javob (bo'lsa) ko'rsatilmoqda.</p>
          ) : null}
          {data.response_text ? (
            <p className="whitespace-pre-wrap text-sm text-foreground" data-testid="response-text">{data.response_text}</p>
          ) : (
            data.has_audio ? null : <p className="text-sm text-foreground/50">Talaba javob yozmagan.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {data.rubric ? `${data.rubric.name} (v${data.rubric.version})` : "Rubrika"}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {!data.rubric ? (
            <p className="text-sm text-destructive" role="alert">Bu komponent uchun rubrika hali sozlanmagan — administrator "Rubrikalar" bo'limida qo'shishi kerak.</p>
          ) : (
            <>
              {!data.rubric.is_validated ? (
                <p className="text-xs text-amber-700">Rubrika tasdiqlanmagan: bu rubrika bilan qo'yilgan ballar "provisional" deb belgilanadi.</p>
              ) : null}
              {data.rubric.instructions ? <p className="whitespace-pre-wrap text-sm text-foreground/70">{data.rubric.instructions}</p> : null}

              {editable ? (
                <>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    {criteria.map((c) => (
                      <div key={c.key}>
                        <label htmlFor={`crit-${c.key}`} className="mb-1 block text-xs font-medium text-foreground/70">
                          {c.label} ({c.min}–{c.max}, qadam {c.step}{c.weight !== "1" ? `, vazn ${c.weight}` : ""})
                        </label>
                        <input
                          id={`crit-${c.key}`}
                          type="text"
                          inputMode="decimal"
                          value={scores[c.key] ?? ""}
                          onChange={(e) => setScores((s) => ({ ...s, [c.key]: e.target.value }))}
                          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                        />
                      </div>
                    ))}
                  </div>
                  <div>
                    <label htmlFor="feedback" className="mb-1 block text-xs font-medium text-foreground/70">Talabaga izoh (talaba ko'radi)</label>
                    <textarea id="feedback" rows={4} maxLength={5000} value={feedback} onChange={(e) => setFeedback(e.target.value)}
                      className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" />
                  </div>
                  <div>
                    <label htmlFor="notes" className="mb-1 block text-xs font-medium text-foreground/70">Ichki izoh (talaba ko'rmaydi)</label>
                    <textarea id="notes" rows={2} maxLength={5000} value={notes} onChange={(e) => setNotes(e.target.value)}
                      className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" />
                  </div>
                  {draft?.revision_number && draft.revision_number > 1 ? (
                    <p className="text-xs text-foreground/60">Tuzatish #{draft.revision_number}: {draft.revision_reason}</p>
                  ) : null}
                  {localError ? <p role="alert" className="text-sm text-destructive">{localError}</p> : null}
                  <div className="flex gap-2">
                    <Button type="button" variant="outline" onClick={handleSave} disabled={saveDraft.isPending}>Qoralamani saqlash</Button>
                    <Button type="button" onClick={handleFinalize} disabled={saveDraft.isPending || finalize.isPending}>Yakunlash</Button>
                  </div>
                </>
              ) : finalized ? (
                <div className="space-y-2">
                  <p className="text-sm text-foreground">
                    Yakuniy ball: <span className="font-semibold" data-testid="final-score">{finalized.reported_score}</span>
                    {finalized.is_provisional ? <span className="ml-2 text-xs text-amber-700">(provisional)</span> : null}
                  </p>
                  <div className="flex flex-wrap items-end gap-2">
                    <div className="flex-1">
                      <label htmlFor="reason" className="mb-1 block text-xs font-medium text-foreground/70">Tuzatish sababi</label>
                      <input id="reason" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={1000}
                        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" />
                    </div>
                    <Button type="button" variant="outline" disabled={reason.trim().length < 3 || revise.isPending}
                      onClick={() => revise.mutate(reason.trim(), { onSuccess: () => setReason("") })}>
                      Tuzatishni boshlash
                    </Button>
                  </div>
                </div>
              ) : null}
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Baholash tarixi</CardTitle></CardHeader>
        <CardContent>
          {data.reviews.length === 0 ? (
            <p className="text-sm text-foreground/50">Hali baho yo'q.</p>
          ) : (
            <ul className="space-y-2" data-testid="review-history">
              {data.reviews.map((r: ReviewOut) => (
                <li key={r.id} className="rounded-md border border-border p-2 text-sm">
                  <span className="font-medium">#{r.revision_number} · {REVIEW_STATUS_LABELS[r.status] ?? r.status}</span>
                  {r.reported_score != null ? ` · ${r.reported_score}` : ""}
                  {r.rubric_version ? ` · rubrika v${r.rubric_version}` : ""}
                  {r.finalized_at ? ` · ${new Date(r.finalized_at).toLocaleString()}` : ""}
                  {r.revision_reason ? <span className="block text-xs text-foreground/60">Sabab: {r.revision_reason}</span> : null}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
