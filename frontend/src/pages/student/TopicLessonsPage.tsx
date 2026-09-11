/**
 * GET /lessons?topic_id=X&status=active — real, public, filtered list.
 * No order_number on Lesson (verified against lessons/schemas.py — the
 * field genuinely does not exist, unlike Topic which has one) — the
 * backend's own default sort (`-created_at`) is used as-is; no ordering
 * UI is built here since there is nothing reliable to order by. This
 * is a real, documented GAP (see docs/Sprint27_...md), not silently
 * worked around with an invented client-side order.
 */
import { useNavigate, useParams } from "react-router-dom";
import { ErrorState } from "@/components/layout/ErrorState";
import { ContentBadges } from "@/components/lessons/ContentBadges";
import { useTopic } from "@/hooks/useTopics";
import { useLessonsList } from "@/hooks/useLessons";

export function TopicLessonsPage() {
  const { topicId } = useParams<{ topicId: string }>();
  const navigate = useNavigate();

  const { data: topic } = useTopic(topicId);
  const { data, isLoading, isError } = useLessonsList({ page: 1, per_page: 100, topic_id: topicId, status: "active" });

  if (!topicId) return null;
  if (isError) return <ErrorState title="Darslar" />;

  return (
    <div>
      <button type="button" onClick={() => navigate(-1)} className="mb-4 text-sm text-primary hover:underline">
        ← Orqaga
      </button>

      <h1 className="mb-6 text-xl font-semibold text-foreground">{topic?.title ?? "Darslar"}</h1>

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
          <p className="text-sm text-foreground/60">Bu mavzu uchun hozircha darslar mavjud emas.</p>
        </div>
      )}
    </div>
  );
}
