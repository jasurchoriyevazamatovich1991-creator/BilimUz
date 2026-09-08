/**
 * Sprint 26 — replaces the PlaceholderPage that stood here since
 * Sprint 13. Cards show REAL, platform-wide counts (Topics, Lessons,
 * Tests, Questions) — verified directly that none of these backend
 * models have a teacher_id/created_by ownership column, so there is no
 * real "only my content" scope to filter by; Teacher genuinely sees
 * the same content pool Admin does, just without Users/Schools/Roles
 * access. No count is fabricated — each uses the same
 * per_page=1-then-read-meta.total pattern already established
 * platform-wide (Sprint 14's dashboard cards, Sprint 20/21's
 * myCount() helpers) rather than inventing a new one.
 */
import { useQuery } from "@tanstack/react-query";
import { DashboardCard } from "@/components/layout/DashboardCard";
import { topicsApi } from "@/api/topics";
import { lessonsApi } from "@/api/lessons";
import { testsApi } from "@/api/tests";
import { questionsApi } from "@/api/questions";

export function TeacherDashboardPage() {
  const topicsCount = useQuery({
    queryKey: ["dashboard", "teacher", "topics-count"],
    queryFn: async () => (await topicsApi.list({ page: 1, per_page: 1 })).meta.total,
  });
  const lessonsCount = useQuery({
    queryKey: ["dashboard", "teacher", "lessons-count"],
    queryFn: async () => (await lessonsApi.list({ page: 1, per_page: 1 })).meta.total,
  });
  const testsCount = useQuery({
    queryKey: ["dashboard", "teacher", "tests-count"],
    queryFn: async () => (await testsApi.list({ page: 1, per_page: 1 })).meta.total,
  });
  const questionsCount = useQuery({
    queryKey: ["dashboard", "teacher", "questions-count"],
    queryFn: async () => (await questionsApi.list({ page: 1, per_page: 1 })).meta.total,
  });

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold text-foreground">Dashboard</h1>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <DashboardCard title="Mavzular" isLoading={topicsCount.isLoading} value={topicsCount.data} />
        <DashboardCard title="Darslar" isLoading={lessonsCount.isLoading} value={lessonsCount.data} />
        <DashboardCard title="Testlar" isLoading={testsCount.isLoading} value={testsCount.data} />
        <DashboardCard title="Savollar" isLoading={questionsCount.isLoading} value={questionsCount.data} />
      </div>
    </div>
  );
}
