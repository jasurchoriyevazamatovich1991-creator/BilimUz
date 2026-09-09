/**
 * The real filtering point: GET /topics?subject_id=X&grade_id=Y,
 * sorted by order_number (real field, verified — the backend's own
 * default sort). Each topic links to its lessons.
 */
import { useNavigate, useParams } from "react-router-dom";
import { ErrorState } from "@/components/layout/ErrorState";
import { useSubject } from "@/hooks/useSubjects";
import { useGrade } from "@/hooks/useGrades";
import { useTopicsList } from "@/hooks/useTopics";

export function StudentSubjectGradeTopicsPage() {
  const { subjectId, gradeId } = useParams<{ subjectId: string; gradeId: string }>();
  const navigate = useNavigate();

  const { data: subject } = useSubject(subjectId);
  const { data: grade } = useGrade(gradeId);
  const { data, isLoading, isError } = useTopicsList({
    page: 1,
    per_page: 100,
    subject_id: subjectId,
    grade_id: gradeId,
    status: "active",
  });

  if (!subjectId || !gradeId) return null;
  if (isError) return <ErrorState title="Mavzular" />;

  return (
    <div>
      <button
        type="button"
        onClick={() => navigate(`/student/subjects/${subjectId}/grades`)}
        className="mb-4 text-sm text-primary hover:underline"
      >
        ← Sinflarga qaytish
      </button>

      <h1 className="mb-6 text-xl font-semibold text-foreground">
        {subject && grade ? `${subject.name} — ${grade.name}` : "Mavzular"}
      </h1>

      {isLoading ? (
        <p className="text-sm text-foreground/50">Yuklanmoqda...</p>
      ) : data && data.items.length > 0 ? (
        <div className="space-y-2">
          {data.items.map((topic) => (
            <button
              key={topic.id}
              type="button"
              onClick={() => navigate(`/student/topics/${topic.id}/lessons`)}
              className="block w-full rounded-lg border border-border bg-card p-4 text-left shadow-xs hover:border-primary/40 hover:shadow-sm"
            >
              <h3 className="font-medium text-foreground">{topic.title}</h3>
              {topic.description ? <p className="mt-1 text-sm text-foreground/60">{topic.description}</p> : null}
            </button>
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-border p-12 text-center">
          <p className="text-sm text-foreground/60">Bu fan va sinf uchun hozircha mavzular mavjud emas.</p>
        </div>
      )}
    </div>
  );
}
