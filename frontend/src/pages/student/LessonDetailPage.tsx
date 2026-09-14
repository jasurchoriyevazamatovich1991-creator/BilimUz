/**
 * Sprint 27 scope boundary (original): `Lesson.video` was shown as a
 * plain, safe external link only.
 *
 * Sprint 35: when `lesson.video_upload_id` is set, a real R2-backed
 * video is preferred and rendered in a native HTML5 <video> player
 * using a short-lived signed URL (GET /uploads/{id}/view-url — the
 * exact same endpoint/authorization Sprint 27 already built; no new
 * endpoint). The signed URL is fetched only when a video_upload_id
 * actually exists (no wasted request otherwise) and is never persisted
 * anywhere — it's held in React Query cache only, matching the
 * existing query pattern, and simply refetched if it ever expires
 * (no separate expiry-tracking logic needed).
 *
 * When `video_upload_id` is NULL, the legacy `Lesson.video` external
 * link behavior is completely unchanged — full backward compatibility
 * for every lesson created before this sprint.
 *
 * Test linkage: there is NO Test<->Lesson relationship on the backend
 * (verified again this sprint — TestListParams/TestOut have topic_id
 * but no lesson_id anywhere). This page therefore looks up tests via
 * the lesson's OWN topic_id (GET /tests?topic_id=X&status=published) —
 * a real, backend-supported bridge — rather than inventing a
 * lesson_id-based relationship that doesn't exist. If a topic has
 * multiple published tests, all are listed; if none, no test section
 * is shown (not silently hidden as an error — an honest empty state).
 * Clicking a test navigates into the EXISTING, unmodified Sprint 20
 * StudentTestDetailPage (/student/tests/:testId), preserving its
 * active-attempt-check / Start-vs-Continue logic exactly as-is.
 */
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/layout/ErrorState";
import { useLesson } from "@/hooks/useLessons";
import { useTestsList } from "@/hooks/useTests";
import { useMyProgress, useCompleteLesson } from "@/hooks/useProgress";
import { uploadsApi } from "@/api/uploads";

function LessonVideoPlayer({ uploadId }: { uploadId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["uploads", "view-url", uploadId],
    queryFn: () => uploadsApi.getViewUrl(uploadId),
  });

  if (isLoading) {
    return <div className="flex aspect-video items-center justify-center rounded-md bg-muted text-sm text-foreground/50">Video yuklanmoqda...</div>;
  }
  if (isError || !data) {
    return <ErrorState title="Video" />;
  }

  return (
    <video
      controls
      preload="metadata"
      className="aspect-video w-full rounded-md bg-black"
      src={data.view_url}
    >
      Brauzeringiz video pleerni qo'llab-quvvatlamaydi.
    </video>
  );
}

export function LessonDetailPage() {
  const { lessonId } = useParams<{ lessonId: string }>();
  const navigate = useNavigate();

  const { data: lesson, isLoading, isError } = useLesson(lessonId);
  const { data: relatedTests } = useTestsList({
    page: 1,
    per_page: 20,
    topic_id: lesson?.topic_id,
    status: "published",
  });
  const { data: progress } = useMyProgress();
  const completeLesson = useCompleteLesson();
  const isCompleted = !!(progress && lessonId && progress.completed_lesson_ids.includes(lessonId));

  if (!lessonId) return null;
  if (isError) return <ErrorState title="Dars" />;
  if (isLoading || !lesson) return <p className="p-6 text-sm text-foreground/50">Yuklanmoqda...</p>;

  return (
    <div className="mx-auto max-w-2xl">
      <button type="button" onClick={() => navigate(-1)} className="mb-4 text-sm text-primary hover:underline">
        ← Orqaga
      </button>

      <Card>
        <CardHeader>
          <CardTitle>{lesson.title}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {lesson.content ? <p className="whitespace-pre-wrap text-sm text-foreground/80">{lesson.content}</p> : null}

          {lesson.video_upload_id ? (
            <div>
              <h3 className="mb-1 text-sm font-medium text-foreground">Video</h3>
              <LessonVideoPlayer uploadId={lesson.video_upload_id} />
            </div>
          ) : lesson.video ? (
            <div>
              <h3 className="mb-1 text-sm font-medium text-foreground">Video</h3>
              <a
                href={lesson.video}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline"
              >
                {lesson.video}
              </a>
            </div>
          ) : null}

          {lesson.pdf ? (
            <div>
              <h3 className="mb-1 text-sm font-medium text-foreground">Material</h3>
              <a href={lesson.pdf} target="_blank" rel="noopener noreferrer" className="text-sm text-primary hover:underline">
                {lesson.pdf}
              </a>
            </div>
          ) : null}

          {relatedTests && relatedTests.items.length > 0 ? (
            <div>
              <h3 className="mb-2 text-sm font-medium text-foreground">Test</h3>
              <div className="space-y-2">
                {relatedTests.items.map((test) => (
                  <button
                    key={test.id}
                    type="button"
                    onClick={() => navigate(`/student/tests/${test.id}`)}
                    className="flex w-full items-center justify-between rounded-md border border-border px-4 py-2 text-left text-sm hover:bg-primary/5"
                  >
                    <span className="text-foreground">{test.title}</span>
                    <span className="text-primary">Testni boshlash →</span>
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          <div className="border-t border-border pt-4">
            {isCompleted ? (
              <span className="inline-flex items-center gap-1.5 rounded-md bg-success/10 px-3 py-2 text-sm font-medium text-success">
                ✓ Tugatildi
              </span>
            ) : (
              <Button
                type="button"
                onClick={() => lessonId && completeLesson.mutate(lessonId)}
                disabled={completeLesson.isPending}
              >
                {completeLesson.isPending ? "Belgilanmoqda..." : "Tugatilgan deb belgilash"}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
