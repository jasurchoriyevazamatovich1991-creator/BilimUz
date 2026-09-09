/**
 * "Darslar" sidebar entry's direct target — a flat, searchable list of
 * ALL active lessons (no subject/grade/topic drill-down required), for
 * a student who wants to browse everything at once rather than
 * navigate the Fan -> Sinf -> Mavzu funnel. GET /lessons?status=active,
 * same real, public, paginated endpoint used by TopicLessonsPage.tsx.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/layout/ErrorState";
import { ContentBadges } from "@/components/lessons/ContentBadges";
import { useLessonsList } from "@/hooks/useLessons";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

const PER_PAGE = 20;

export function StudentLessonsPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const debouncedSearch = useDebouncedValue(searchInput, 400);

  const { data, isLoading, isError } = useLessonsList({
    page,
    per_page: PER_PAGE,
    search: debouncedSearch || undefined,
    status: "active",
  });

  if (isError) return <ErrorState title="Darslar" />;

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold text-foreground">Darslar</h1>

      <Input
        placeholder="Qidirish..."
        value={searchInput}
        onChange={(e) => {
          setSearchInput(e.target.value);
          setPage(1);
        }}
        className="mb-4 max-w-xs"
      />

      {isLoading ? (
        <p className="text-sm text-foreground/50">Yuklanmoqda...</p>
      ) : data && data.items.length > 0 ? (
        <div className="space-y-2">
          {data.items.map((lesson) => (
            <button
              key={lesson.id}
              type="button"
              onClick={() => navigate(`/student/lessons/${lesson.id}`)}
              className="flex w-full items-center justify-between rounded-lg border border-border bg-card p-4 text-left shadow-xs hover:border-primary/40 hover:shadow-sm"
            >
              <span className="font-medium text-foreground">{lesson.title}</span>
              <ContentBadges video={lesson.video} pdf={lesson.pdf} content={lesson.content} />
            </button>
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-border p-12 text-center">
          <p className="text-sm text-foreground/60">Hozircha darslar mavjud emas.</p>
        </div>
      )}

      {data && data.meta.total_pages > 1 ? (
        <div className="mt-4 flex items-center justify-between text-sm text-foreground/60">
          <span>{data.meta.total} tadan {(page - 1) * PER_PAGE + 1}-{Math.min(page * PER_PAGE, data.meta.total)}</span>
          <div className="flex gap-2">
            <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="rounded-md border border-border px-3 py-1.5 disabled:opacity-40">Oldingi</button>
            <button type="button" disabled={page >= data.meta.total_pages} onClick={() => setPage((p) => p + 1)} className="rounded-md border border-border px-3 py-1.5 disabled:opacity-40">Keyingi</button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
