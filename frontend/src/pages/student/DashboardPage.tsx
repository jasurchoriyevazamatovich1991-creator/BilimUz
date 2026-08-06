import { DashboardCard } from "@/components/layout/DashboardCard";
import { ErrorState } from "@/components/layout/ErrorState";
import { useStudentDashboardStats } from "@/hooks/useDashboardStats";

/**
 * Shared by Student and Applicant (same layout). Widget set per the
 * approved Sprint 14 scope: "Assigned Tests", Results, Certificates.
 * NOTE: there is no "assignment" concept anywhere in the backend
 * schema (verified) — "Mavjud testlar" reads the same published-tests
 * catalog every authenticated user sees, labeled honestly rather than
 * implying a targeting feature that doesn't exist.
 */
export function StudentDashboardPage() {
  const { availableTestsCount, resultsCount, certificatesCount } = useStudentDashboardStats();

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold text-foreground">Dashboard</h1>
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
