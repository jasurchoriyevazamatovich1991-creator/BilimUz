/**
 * ARCHITECTURE NOTE: Grade has no subject relationship on the backend
 * (verified — GradeOut/GradeListParams carry no subject_id at all).
 * This page therefore shows the same full Grade list regardless of
 * which subject was picked — real filtering only becomes meaningful
 * once BOTH subject_id and grade_id are chosen together, at the Topics
 * step (Topic is the actual subject+grade junction). This step exists
 * to match the requested Fan -> Sinf -> Mavzu navigation shape, not
 * because Grade itself is subject-scoped.
 */
import { useNavigate, useParams } from "react-router-dom";
import { ErrorState } from "@/components/layout/ErrorState";
import { useSubject } from "@/hooks/useSubjects";
import { useGradesList } from "@/hooks/useGrades";

export function StudentSubjectGradesPage() {
  const { subjectId } = useParams<{ subjectId: string }>();
  const navigate = useNavigate();

  const { data: subject } = useSubject(subjectId);
  const { data, isLoading, isError } = useGradesList({ page: 1, per_page: 100, status: "active" });

  if (!subjectId) return null;
  if (isError) return <ErrorState title="Sinflar" />;

  return (
    <div>
      <button type="button" onClick={() => navigate("/student/subjects")} className="mb-4 text-sm text-primary hover:underline">
        ← Fanlarga qaytish
      </button>

      <h1 className="mb-6 text-xl font-semibold text-foreground">
        {subject ? `${subject.name} — sinf tanlang` : "Sinf tanlang"}
      </h1>

      {isLoading ? (
        <p className="text-sm text-foreground/50">Yuklanmoqda...</p>
      ) : data && data.items.length > 0 ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {data.items.map((grade) => (
            <button
              key={grade.id}
              type="button"
              onClick={() => navigate(`/student/subjects/${subjectId}/grades/${grade.id}/topics`)}
              className="rounded-lg border border-border bg-card p-5 text-center font-medium text-foreground shadow-xs hover:border-primary/40 hover:shadow-sm"
            >
              {grade.name}
            </button>
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-border p-12 text-center">
          <p className="text-sm text-foreground/60">Hozircha sinflar mavjud emas.</p>
        </div>
      )}
    </div>
  );
}
