import { DashboardCard } from "@/components/layout/DashboardCard";
import { ErrorState } from "@/components/layout/ErrorState";
import { useStudentDashboardStats } from "@/hooks/useDashboardStats";
import { useMyProgress } from "@/hooks/useProgress";

/**
 * Shared by Student and Applicant (same layout). Widget set per the
 * approved Sprint 14 scope: "Assigned Tests", Results, Certificates.
 * NOTE: there is no "assignment" concept anywhere in the backend
 * schema (verified) — "Mavjud testlar" reads the same published-tests
 * catalog every authenticated user sees, labeled honestly rather than
 * implying a targeting feature that doesn't exist.
 *
 * Sprint 36: added a real "O'quv jarayoni" (Learning Progress) card —
 * X/Y lessons completed, Z% — sourced entirely from the real
 * GET /progress/me endpoint (the exact same query LessonDetailPage's
 * completion control already uses, so navigating between them never
 * causes a duplicate request; TanStack Query serves both from the same
 * cached ["progress", "me"] entry). No fake percentage, no
 * client-computed guess.
 */
export function StudentDashboardPage() {
  const { availableTestsCount, resultsCount, certificatesCount } = useStudentDashboardStats();
  const { data: progress, isLoading: isProgressLoading, isError: isProgressError } = useMyProgress();

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold text-foreground">Dashboard</h1>

      {isProgressError ? (
        <div className="mb-6"><ErrorState title="O'quv jarayoni" /></div>
      ) : (
        <div className="mb-6 rounded-lg border border-border bg-card p-4">
          <h2 className="mb-2 text-sm font-medium text-foreground">O'quv jarayoni</h2>
          {isProgressLoading ? (
            <p className="text-sm text-foreground/50">Yuklanmoqda...</p>
          ) : progress ? (
            <>
              <p className="text-sm text-foreground/70">
                Tugatilgan: {progress.completed_lessons} / {progress.total_lessons} dars
              </p>
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${progress.percentage}%` }} />
              </div>
              <p className="mt-1 text-xs text-foreground/50">{progress.percentage}%</p>
            </>
          ) : null}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {availableTestsCount.isError ? (
          <ErrorState title="Mavjud testlar" />
        ) : (
          <DashboardCard title="Mavjud testlar" isLoading={availableTestsCount.isLoading} value={availableTestsCount.data} />
        )}
        {resultsCount.isError ? (
          <ErrorState title="Mening natijalarim" />
        ) : (
          <DashboardCard title="Mening natijalarim" isLoading={resultsCount.isLoading} value={resultsCount.data} />
        )}
        {certificatesCount.isError ? (
          <ErrorState title="Sertifikatlarim" />
        ) : (
          <DashboardCard title="Sertifikatlarim" isLoading={certificatesCount.isLoading} value={certificatesCount.data} />
        )}
      </div>
    </div>
  );
}
