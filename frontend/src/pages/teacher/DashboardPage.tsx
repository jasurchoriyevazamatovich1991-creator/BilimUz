import { DashboardCard } from "@/components/layout/DashboardCard";
import { ErrorState } from "@/components/layout/ErrorState";
import { useTeacherDashboardStats } from "@/hooks/useDashboardStats";

/**
 * Widget set per the approved Sprint 14 scope: Subjects, Lessons,
 * Tests, Results. NOTE: "Natijalar" here reads GET /results/me, which
 * is scoped to the LOGGED-IN USER's own results regardless of role
 * (verified against backend/app/modules/results/router.py) — for a
 * Teacher this shows their own results as a test-taker, not results of
 * students they teach (no such endpoint exists). Labeled accordingly.
 */
export function TeacherDashboardPage() {
  const { subjectsCount, lessonsCount, testsCount, resultsCount } = useTeacherDashboardStats();

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold text-foreground">Dashboard</h1>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {subjectsCount.isError ? (
          <ErrorState title="Fanlar" />
        ) : (
          <DashboardCard title="Fanlar" isLoading={subjectsCount.isLoading} value={subjectsCount.data} />
        )}
        {lessonsCount.isError ? (
          <ErrorState title="Darslar" />
        ) : (
          <DashboardCard title="Darslar" isLoading={lessonsCount.isLoading} value={lessonsCount.data} />
        )}
        {testsCount.isError ? (
          <ErrorState title="Nashr qilingan testlar" />
        ) : (
          <DashboardCard title="Nashr qilingan testlar" isLoading={testsCount.isLoading} value={testsCount.data} />
        )}
        {resultsCount.isError ? (
          <ErrorState title="Mening natijalarim" />
        ) : (
          <DashboardCard title="Mening natijalarim" isLoading={resultsCount.isLoading} value={resultsCount.data} />
        )}
      </div>
    </div>
  );
}
