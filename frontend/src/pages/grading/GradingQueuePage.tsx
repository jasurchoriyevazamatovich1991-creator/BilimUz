/**
 * Task 5 — grading queue for manually scored exam responses (IELTS
 * Writing/Speaking, GRE AWA). Shared by the Admin and Teacher panels;
 * access is decided by the backend GRADE_SUBMISSIONS permission, so a
 * user without it sees an explanation instead of data.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/api/client";
import type { QueueStatus } from "@/api/grading";
import { useGradingQueue } from "@/hooks/useGrading";
import { MANUAL_COMPONENT_LABELS, QUEUE_STATUS_LABELS } from "@/lib/grading";

const FILTERS: { value: QueueStatus | undefined; label: string }[] = [
  { value: "pending", label: "Baholanmagan" },
  { value: "draft", label: "Qoralama" },
  { value: "finalized", label: "Yakunlangan" },
  { value: undefined, label: "Hammasi" },
];

export function GradingQueuePage({ basePath = "/admin" }: { basePath?: string }) {
  const navigate = useNavigate();
  const [status, setStatus] = useState<QueueStatus | undefined>("pending");
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, error } = useGradingQueue(status, page);
  const forbidden = error instanceof ApiError && error.status === 403;
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.per_page)) : 1;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-foreground">Baholash</h1>
      <p className="text-sm text-foreground/60">IELTS Writing, IELTS Speaking va GRE Analytical Writing javoblarini rubrika bo'yicha baholash.</p>

      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Holat bo'yicha filtr">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            role="tab"
            aria-selected={status === f.value}
            onClick={() => { setStatus(f.value); setPage(1); }}
            className={`rounded-md border px-3 py-1 text-sm ${status === f.value ? "border-primary bg-primary/10 text-primary" : "border-border text-foreground/70"}`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Javoblar{data ? ` (${data.total})` : ""}</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-foreground/50">Yuklanmoqda...</p>
          ) : forbidden ? (
            <p className="text-sm text-destructive" role="alert">
              Sizda javoblarni baholash ruxsati (GRADE_SUBMISSIONS) yo'q. Administrator uni rolingizga "Rollar" bo'limida berishi mumkin.
            </p>
          ) : isError || !data ? (
            <p className="text-sm text-destructive" role="alert">Navbatni yuklab bo'lmadi</p>
          ) : data.items.length === 0 ? (
            <p className="text-sm text-foreground/50">Bu holatda javob yo'q.</p>
          ) : (
            <ul className="divide-y divide-border">
              {data.items.map((item) => (
                <li key={`${item.attempt_id}-${item.question_id}`} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <div>
                    <p className="font-medium text-foreground">{item.test_title} · {item.section_name}</p>
                    <p className="text-xs text-foreground/50">
                      {MANUAL_COMPONENT_LABELS[item.score_component]} · {QUEUE_STATUS_LABELS[item.status]}
                      {item.reported_score != null ? ` · ${item.reported_score}` : ""}
                      {item.finished_at ? ` · ${new Date(item.finished_at).toLocaleString()}` : ""}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => navigate(`${basePath}/grading/${item.attempt_id}/${item.question_id}`)}
                    className="text-sm text-primary hover:underline"
                  >
                    {item.status === "finalized" ? "Ko'rish" : "Baholash"}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {data && totalPages > 1 ? (
            <div className="mt-3 flex items-center justify-end gap-2 text-sm">
              <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="rounded border border-border px-2 py-1 disabled:opacity-40">Oldingi</button>
              <span>{page} / {totalPages}</span>
              <button type="button" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} className="rounded border border-border px-2 py-1 disabled:opacity-40">Keyingi</button>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
