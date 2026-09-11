/**
 * Sprint 27 scope boundary (explicit): `Lesson.video` is shown as a
 * plain, safe external link — NOT embedded, no YouTube/Vimeo provider
 * detection, no <video> tag, no player UI. Building a real player is
 * Sprint 28's job; this page does not exceed what `Lesson.video`
 * actually is today (a raw URL string, verified against
 * lessons/schemas.py).
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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/layout/ErrorState";
import { useLesson } from "@/hooks/useLessons";
import { useTestsList } from "@/hooks/useTests";

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

          {lesson.video ? (
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
        </CardContent>
      </Card>
    </div>
  );
}
