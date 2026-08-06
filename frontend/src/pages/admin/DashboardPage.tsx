import { DashboardCard } from "@/components/layout/DashboardCard";
import { ErrorState } from "@/components/layout/ErrorState";
import { UnavailableState } from "@/components/layout/UnavailableState";
import { useAdminDashboardStats } from "@/hooks/useDashboardStats";

/**
 * Widget set per the approved Sprint 14 scope: Users, Schools, Learning
 * Centers, Subjects, Tests, Payments, Results. "Payments" shows active
 * plan count (real data — see api/payments.ts for why, no admin-wide
 * transaction endpoint exists). "Natijalar" has no admin-wide backend
 * endpoint at all (only /results/me, own-data) — shown honestly via
 * UnavailableState rather than faked or silently dropped from the
 * approved list.
 */
export function AdminDashboardPage() {
  const { usersCount, schoolsCount, learningCentersCount, subjectsCount, testsCount, activePlansCount } =
    useAdminDashboardStats();

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold text-foreground">Boshqaruv paneli</h1>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {usersCount.isError ? (
          <ErrorState title="Foydalanuvchilar" />
        ) : (
          <DashboardCard title="Foydalanuvchilar" isLoading={usersCount.isLoading} value={usersCount.data} />
        )}
        {schoolsCount.isError ? (
          <ErrorState title="Maktablar" />
        ) : (
          <DashboardCard title="Maktablar" isLoading={schoolsCount.isLoading} value={schoolsCount.data} />
        )}
        {learningCentersCount.isError ? (
          <ErrorState title="O'quv markazlari" />
        ) : (
          <DashboardCard title="O'quv markazlari" isLoading={learningCentersCount.isLoading} value={learningCentersCount.data} />
        )}
        {subjectsCount.isError ? (
          <ErrorState title="Fanlar" />
        ) : (
          <DashboardCard title="Fanlar" isLoading={subjectsCount.isLoading} value={subjectsCount.data} />
        )}
        {testsCount.isError ? (
          <ErrorState title="Nashr qilingan testlar" />
        ) : (
          <DashboardCard title="Nashr qilingan testlar" isLoading={testsCount.isLoading} value={testsCount.data} />
        )}
        {activePlansCount.isError ? (
          <ErrorState title="To'lov rejalari" />
        ) : (
          <DashboardCard title="To'lov rejalari" isLoading={activePlansCount.isLoading} value={activePlansCount.data} />
        )}
        <UnavailableState title="Natijalar" />
      </div>
    </div>
  );
}
